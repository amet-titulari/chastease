"""Persistent WebSocket client for the OTC (open-DGLAB-controller) E-Stim device.

The client runs an asyncio event loop in a dedicated daemon thread.
Commands are enqueued from synchronous FastAPI handlers via
``send_otc_command()``.  The inner loop reconnects automatically after
any connection failure.
"""

import asyncio
import json
import logging
import threading

logger = logging.getLogger("uvicorn.error")

# ---- module-level state (protected by _lock) ----
_lock = threading.Lock()
_thread: threading.Thread | None = None
_loop: asyncio.AbstractEventLoop | None = None
_queue: asyncio.Queue | None = None
_running = False
_current_url: str | None = None
_connected = False


# ---- public API ----

def start_otc_client(url: str) -> None:
    """Start (or restart) the background client pointing at *url*."""
    global _thread, _loop, _queue, _running, _current_url, _connected

    with _lock:
        if _running and _current_url == url:
            return  # already running with the same URL – nothing to do

        # Stop any previous client first.
        _stop_unlocked()

        _running = True
        _current_url = url
        _connected = False

        loop = asyncio.new_event_loop()
        queue: asyncio.Queue = asyncio.Queue()
        _loop = loop
        _queue = queue

        t = threading.Thread(
            target=_run_event_loop,
            args=(loop, url, queue),
            daemon=True,
            name="otc-client",
        )
        _thread = t

    t.start()
    logger.info("OTC client started → %s", url)


def stop_otc_client() -> None:
    """Gracefully stop the background client."""
    with _lock:
        _stop_unlocked()
    logger.info("OTC client stopped.")


def send_otc_command(cmd: dict) -> bool:
    """Enqueue *cmd* for delivery over the WebSocket.

    Returns ``True`` if the command was queued, ``False`` if the client is
    not running.
    """
    with _lock:
        if not _running or _loop is None or _queue is None:
            return False
        loop = _loop
        queue = _queue

    asyncio.run_coroutine_threadsafe(queue.put(cmd), loop)
    return True


def otc_status() -> dict:
    """Return a snapshot of the current client state."""
    with _lock:
        return {
            "running": _running,
            "connected": _connected,
            "url": _current_url,
        }


# ---- internals ----

def _stop_unlocked() -> None:
    """Must be called with *_lock* held."""
    global _running, _thread, _loop, _queue, _connected, _current_url

    if not _running:
        return

    _running = False
    _connected = False

    # Wake the event loop so it can exit cleanly.
    if _loop is not None:
        _loop.call_soon_threadsafe(_loop.stop)

    _thread = None
    _loop = None
    _queue = None


def _run_event_loop(loop: asyncio.AbstractEventLoop, url: str, queue: asyncio.Queue) -> None:
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_client_main(url, queue))
    finally:
        loop.close()


async def _client_main(url: str, queue: asyncio.Queue) -> None:
    """Outer reconnect loop."""
    import websockets  # imported lazily so the module loads even without the dep

    global _connected

    while True:
        with _lock:
            if not _running:
                break

        try:
            logger.info("OTC: connecting to %s", url)
            async with websockets.connect(url, open_timeout=10, ping_interval=20) as ws:
                with _lock:
                    _connected = True
                logger.info("OTC: connected to %s", url)

                async def _sender() -> None:
                    while True:
                        cmd = await queue.get()
                        try:
                            await ws.send(json.dumps(cmd, ensure_ascii=False))
                            logger.debug("OTC sent: %s", cmd)
                        except Exception as exc:
                            logger.warning("OTC send error: %s", exc)
                            break

                async def _receiver() -> None:
                    async for _ in ws:
                        pass  # discard inbound frames

                sender_task = asyncio.create_task(_sender())
                receiver_task = asyncio.create_task(_receiver())
                done, pending = await asyncio.wait(
                    {sender_task, receiver_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for t in pending:
                    t.cancel()

        except Exception as exc:
            logger.warning("OTC connection error: %s", exc)
        finally:
            with _lock:
                _connected = False

        with _lock:
            if not _running:
                break

        logger.info("OTC: reconnecting in 5 s…")
        await asyncio.sleep(5)
