#benutzer/qrcode.py
import qrcode
import uuid

from flask import current_app
from flask_login import current_user

from helper.log_config import logger


def generate_qr():


    qr_uuid    = str(uuid.uuid4())
    qr_base    = current_app.config['BASE_URL']

    data    = qr_base + '/user/ttl_open/' + qr_uuid

    try:

        # QR-Code erstellen
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        # QR-Code Bild erstellen
        img = qr.make_image(fill_color="black", back_color="white")

        # QR-Code speichern
        img.save(f"qrcodes/{qr_uuid}.png")

        logger.info('QRCode generated!')

        return {'success': True, 'qr_uuid': qr_uuid}
    
    except:
        # Hier könnten Sie detailliertere Fehlermeldungen basierend auf dem spezifischen Fehler hinzufügen
        return {'success': False, 'error': f'QR Nicht erstellt:'}
