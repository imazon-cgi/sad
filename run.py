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



if __name__ == "__main__":
    from flask import Flask
    srv = Flask(__name__)
    dash_app = register_sad_degradacao_assentamento(srv)
    dash_app2 = register_sad_degradacao_estados(srv)
    dash_app3 = register_sad_degradacao_municipio(srv)
    dash_app4 = register_sad_degradacao_terras_indigenas(srv)
    dash_app5 = register_sad_degradacao_uc(srv)
    dash_app6 = register_sad_desmatamento_assentamento(srv)
    dash_app7 = register_sad_desmatamento_estados(srv)
    dash_app8 = register_sad_desmatamento_municipios(srv)
    dash_app9 = register_sad_desmatamento_terras_indigenas(srv)
    dash_app10 = register_sad_desmatamento_uc(srv)
    srv.run(debug=True, port=8051)
