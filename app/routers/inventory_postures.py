from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers import games

router = APIRouter(prefix="/api/inventory/postures", tags=["inventory"])


@router.get("/modules/{module_key}")
def list_module_postures(
    module_key: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    return games.list_module_postures(module_key=module_key, request=request, db=db, response=response)


@router.get("/modules/{module_key}/available")
def list_available_module_postures(
    module_key: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    return games.list_available_module_postures(module_key=module_key, request=request, db=db, response=response)


@router.post("/modules/{module_key}")
def create_module_posture(
    module_key: str,
    payload: games.PostureTemplateCreateRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    return games.create_module_posture(module_key=module_key, payload=payload, request=request, db=db, response=response)


@router.put("/modules/{module_key}/{posture_id}")
def update_module_posture(
    module_key: str,
    posture_id: int,
    payload: games.PostureTemplateUpdateRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    return games.update_module_posture(module_key=module_key, posture_id=posture_id, payload=payload, request=request, db=db, response=response)


@router.delete("/modules/{module_key}/{posture_id}")
def delete_module_posture(
    module_key: str,
    posture_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    return games.delete_module_posture(module_key=module_key, posture_id=posture_id, request=request, db=db, response=response)


@router.put("/modules/{module_key}/{posture_id}/reference-pose")
def update_module_posture_reference_pose(
    module_key: str,
    posture_id: int,
    payload: games.PostureReferencePoseUpdateRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    return games.update_module_posture_reference_pose(
        module_key=module_key, posture_id=posture_id, payload=payload, request=request, db=db, response=response
    )


@router.put("/modules/{module_key}/{posture_id}/reference-pose/manual")
def update_module_posture_reference_pose_manual(
    module_key: str,
    posture_id: int,
    payload: games.PostureReferencePoseManualUpdateRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    return games.update_module_posture_reference_pose_manual(
        module_key=module_key,
        posture_id=posture_id,
        payload=payload,
        request=request,
        db=db,
        response=response,
    )


@router.post("/modules/{module_key}/{posture_id}/reference-pose/upload-image")
async def upload_module_posture_reference_pose_image(
    module_key: str,
    posture_id: int,
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    return await games.upload_module_posture_reference_pose_image(
        module_key=module_key,
        posture_id=posture_id,
        request=request,
        file=file,
        db=db,
        response=response,
    )


@router.post("/modules/{module_key}/upload-image")
async def upload_module_posture_image(
    module_key: str,
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    return await games.upload_module_posture_image(module_key=module_key, request=request, file=file, db=db, response=response)


@router.get("/modules/{module_key}/export")
def export_module_postures_zip(
    module_key: str,
    request: Request,
    db: Session = Depends(get_db),
):
    return games.export_module_postures_zip(module_key=module_key, request=request, db=db)


@router.post("/modules/{module_key}/import-zip")
async def import_module_postures_zip(
    module_key: str,
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    return await games.import_module_postures_zip(module_key=module_key, request=request, file=file, db=db, response=response)


@router.get("/matrix")
def list_posture_matrix(request: Request, db: Session = Depends(get_db)) -> dict:
    return games.list_posture_matrix(request=request, db=db)


@router.put("/matrix")
def update_posture_matrix(
    payload: games.PostureMatrixBulkUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    return games.update_posture_matrix(payload=payload, request=request, db=db)
