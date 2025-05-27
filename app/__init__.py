from app.dashboards.sad_degradacao_assentamentos import (
    register_sad_degradacao_assentamento,
)
from app.dashboards.sad_degradacao_estados import (
    register_sad_degradacao_estados,
)
from app.dashboards.sad_degradacao_municipios import (
    register_sad_degradacao_municipio,
)

from app.dashboards.sad_degradacao_terras_indigenas import (
    register_sad_degradacao_terras_indigenas,
)

from app.dashboards.sad_degradacao_uc import (
    register_sad_degradacao_uc,
)
from app.dashboards.sad_desmatamento_assentamento import (
    register_sad_desmatamento_assentamento,
)

from app.dashboards.sad_desmatamento_estados import (
    register_sad_desmatamento_estados,
)

from app.dashboards.sad_desmatamento_municipios import (
    register_sad_desmatamento_municipios,
)
from app.dashboards.sad_desmatamento_terras_indigenas import (
    register_sad_desmatamento_terras_indigenas,
)
from app.dashboards.sad_desmatamento_uc import (
    register_sad_desmatamento_uc,
)

def create_app():
    from flask import Flask
    server = Flask(__name__)
    
    register_sad_degradacao_assentamento(server)
    register_sad_degradacao_estados(server)
    register_sad_degradacao_municipio(server)
    register_sad_degradacao_terras_indigenas(server)
    register_sad_degradacao_uc(server)
    register_sad_desmatamento_assentamento(server)
    register_sad_desmatamento_estados(server)
    register_sad_desmatamento_municipios(server)
    register_sad_desmatamento_terras_indigenas(server)
    register_sad_desmatamento_uc(server)

    return server
