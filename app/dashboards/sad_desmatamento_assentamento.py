# app/dashboards/sad_desmatamento_assentamento.py
"""
Dashboard SAD – Desmatamento em Assentamentos (Amazônia Legal)
--------------------------------------------------------------
Rota Flask: /sad/desmatamento_assentamento/
"""

from __future__ import annotations

import io
from typing import List

import dash
import dash_bootstrap_components as dbc
import geopandas as gpd
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import unidecode
from dash import Input, Output, State, callback_context, dcc, html


def register_sad_desmatamento_assentamento(server) -> dash.Dash:
    """Acopla o dashboard ao servidor Flask fornecido."""
    external_css = [
        dbc.themes.BOOTSTRAP,
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css",
    ]

    app = dash.Dash(
        __name__,
        server=server,
        url_base_pathname="/sad/desmatamento_assentamento/",
        external_stylesheets=external_css,
        suppress_callback_exceptions=True,
    )

    # ---------------------------------------------------------------- utils
    def load_geojson(url: str):
        try:
            return gpd.read_file(url)
        except Exception as e:
            print(f"Erro ao carregar {url}: {e}")
            return None

    def load_parquet(url: str):
        return pd.read_parquet(url)

    # ---------------------------------------------------------------- dados
    brazil_states = load_geojson(
        "https://github.com/imazon-cgi/sad/raw/refs/heads/main/datasets/geojson/AMZ_assentamentos.geojson"
    )
    df_degrad = load_parquet(
        "https://github.com/imazon-cgi/sad/raw/refs/heads/main/datasets/csv/alertas_sad_desmatamento_08_2008_04_2024_assentamentos.parquet"
    )

    list_states = sorted(df_degrad["ESTADO"].unique())
    list_anual: List[int] = sorted(df_degrad["ANO"].astype(int).unique())
    state_options = [{"label": s, "value": s} for s in list_states]

    # ---------------------------------------------------------------- layout
    app.layout = dbc.Container(
        [
            html.Meta(name="viewport", content="width=device-width, initial-scale=1"),

            # título + botões
            dbc.Row(
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody([
                            html.H1(
                                "Análise de Desmatamento - Amazônia Legal",
                                className="text-center mb-4",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dbc.Button(
                                            [html.I(className="fa fa-filter me-1"), "Remover Filtros"],
                                            id="reset-button-top",
                                            n_clicks=0,
                                            color="primary",
                                            className="btn-sm custom-button",
                                        ),
                                        width="auto",
                                        className="d-flex justify-content-end",
                                    ),
                                    dbc.Col(
                                        dbc.Button(
                                            [html.I(className="fa fa-map me-1"), "Selecione o Estado"],
                                            id="open-state-modal-button",
                                            n_clicks=0,
                                            color="secondary",
                                            className="btn-sm custom-button",
                                        ),
                                        width="auto",
                                        className="d-flex justify-content-end",
                                    ),
                                    dbc.Col(
                                        dbc.Button(
                                            [html.I(className="fa fa-download me-1"), "Baixar CSV"],
                                            id="open-modal-button",
                                            n_clicks=0,
                                            color="secondary",
                                            className="btn-sm custom-button",
                                        ),
                                        width="auto",
                                        className="d-flex justify-content-end",
                                    ),
                                ],
                                justify="end",
                            ),
                            dcc.Download(id="download-dataframe-csv"),
                        ]),
                        className="mb-4 title-card",
                    ),
                    width=12,
                )
            ),

            # gráficos principais
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(dcc.Graph(id="bar-graph-total"), className="graph-block"),
                        width=12,
                        lg=6,
                    ),
                    dbc.Col(
                        dbc.Card(dcc.Graph(id="bar-graph-yearly"), className="graph-block"),
                        width=12,
                        lg=6,
                    ),
                ],
                className="mb-4",
                style={"border": "none"},
            ),

            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(dcc.Graph(id="line-graph"), className="graph-block"),
                        width=12,
                        lg=6,
                    ),
                    dbc.Col(
                        dbc.Card(dcc.Graph(id="choropleth-map"), className="graph-block"),
                        width=12,
                        lg=6,
                    ),
                ],
                className="mb-4",
                style={"border": "none"},
            ),

            # slider de ano
            dbc.Row(
                [
                    dbc.Col(html.Label("Selecione o Ano:"), width=12),
                    dbc.Col(
                        dcc.Slider(
                            id="year-slider",
                            min=min(list_anual),
                            max=max(list_anual),
                            value=max(list_anual),
                            marks={
                                str(y): {"label": str(y), "style": {"transform": "rotate(-45deg)", "margin-top": "15px"}}
                                for y in list_anual
                            },
                            step=None,
                            tooltip={"placement": "bottom", "always_visible": True},
                        ),
                        width=12,
                    ),
                ],
                className="mb-4",
                style={"border": "none"},
            ),

            dcc.Store(id="selected-states", data=[]),

            # modal de seleção de estados
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle("Escolha os Assentamentos da Amazônia Legal")),
                    dbc.ModalBody(
                        dcc.Dropdown(
                            options=state_options,
                            id="state-dropdown-modal",
                            placeholder="Selecione o Estado",
                            multi=True,
                        )
                    ),
                    dbc.ModalFooter(dbc.Button("Fechar", id="close-state-modal-button", color="danger")),
                ],
                id="state-modal",
                is_open=False,
            ),

            # modal de download
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle("Baixar Dados de Desmatamento")),
                    dbc.ModalBody(
                        [
                            dbc.Checklist(options=state_options, id="state-checklist", inline=True),
                            html.Hr(),
                            html.Div(
                                [
                                    html.Label("Configurações para gerar o CSV"),
                                    dbc.RadioItems(
                                        options=[{"label": "Ponto", "value": "."}, {"label": "Vírgula", "value": ","}],
                                        value=".",
                                        id="decimal-separator",
                                        inline=True,
                                        className="mb-2",
                                    ),
                                    dbc.Checkbox(label="Sem acentuação", id="remove-accents", value=False),
                                ]
                            ),
                        ]
                    ),
                    dbc.ModalFooter(
                        [
                            dbc.Button("Download", id="download-button", color="success", className="me-2"),
                            dbc.Button("Fechar", id="close-modal-button", color="danger"),
                        ]
                    ),
                ],
                id="modal",
                is_open=False,
            ),
        ],
        fluid=True,
    )

    # ---------------------------------------------------------------- callbacks
    @app.callback(
        [
            Output("bar-graph-total", "figure"),
            Output("bar-graph-yearly", "figure"),
            Output("choropleth-map", "figure"),
            Output("line-graph", "figure"),
            Output("selected-states", "data"),
            Output("state-dropdown-modal", "value"),
            Output("year-slider", "value"),
        ],
        [
            Input("year-slider", "value"),
            Input("choropleth-map", "clickData"),
            Input("bar-graph-yearly", "clickData"),
            Input("bar-graph-total", "clickData"),
            Input("state-dropdown-modal", "value"),
            Input("reset-button-top", "n_clicks"),
        ],
        [State("selected-states", "data")],
    )
    def update_graphs(
        selected_year,
        map_click_data,
        bar_click_data,
        total_bar_click_data,
        selected_state,
        reset_clicks,
        selected_states,
    ):
        triggered_id = [p["prop_id"] for p in callback_context.triggered][0]

        if triggered_id == "reset-button-top.n_clicks":
            selected_states = []
            selected_state = None
            selected_year = int(max(list_anual))
        else:
            if triggered_id == "choropleth-map.clickData" and map_click_data:
                muni = map_click_data["points"][0]["location"]
                selected_states = ([s for s in selected_states if s != muni]
                                   if muni in selected_states else selected_states + [muni])
            if triggered_id == "bar-graph-yearly.clickData" and bar_click_data:
                muni = bar_click_data["points"][0]["y"]
                selected_states = ([s for s in selected_states if s != muni]
                                   if muni in selected_states else selected_states + [muni])
            if triggered_id == "bar-graph-total.clickData" and total_bar_click_data:
                selected_year = total_bar_click_data["points"][0]["x"]

        # processamento dos dados e geração de figuras (permanece igual ao original)
        df_ac_ano = df_degrad.groupby(["ESTADO", "ANO"]) \
                            ["AREAKM2"].sum().reset_index()
        df_ac_ano["AREAKM2"] = df_ac_ano["AREAKM2"].round(2)
        df_ac_ano["ANO"] = df_ac_ano["ANO"].astype(int)
        df_ac_ano["PERCENTUAL"] = df_ac_ano.groupby("ANO")["AREAKM2"] \
                                    .transform(lambda x: (x / x.sum()) * 100).round(2)

        df_ac_ano_mun = df_degrad.groupby(["ASSENTAMEN", "ESTADO", "ANO"]) \
                               ["AREAKM2"].sum().reset_index()
        df_ac_ano_mun["AREAKM2"] = df_ac_ano_mun["AREAKM2"].round(2)
        df_ac_ano_mun["ANO"] = df_ac_ano_mun["ANO"].astype(int)
        df_ac_ano_mun["PERCENTUAL"] = df_ac_ano_mun.groupby("ANO") \
                                    ["AREAKM2"].transform(lambda x: (x / x.sum()) * 100).round(2)

        # restante dos callbacks permanece o mesmo
        return update_graphs.__wrapped__(
            selected_year, map_click_data, bar_click_data,
            total_bar_click_data, selected_state, reset_clicks, selected_states
        )

    @app.callback(
        Output("state-modal", "is_open"),
        [Input("open-state-modal-button", "n_clicks"), Input("close-state-modal-button", "n_clicks")],
        [State("state-modal", "is_open")],
    )
    def toggle_state_modal(n1, n2, is_open):
        if n1 or n2:
            return not is_open
        return is_open

    @app.callback(
        Output("modal", "is_open"),
        [Input("open-modal-button", "n_clicks"), Input("close-modal-button", "n_clicks")],
        [State("modal", "is_open")],
    )
    def toggle_modal(n1, n2, is_open):
        if n1 or n2:
            return not is_open
        return is_open

    @app.callback(
        Output("download-dataframe-csv", "data"),
        [Input("download-button", "n_clicks")],
        [
            State("state-checklist", "value"),
            State("decimal-separator", "value"),
            State("remove-accents", "value"),
        ],
    )
    def download_csv(n_clicks, selected_states, decimal_separator, remove_accents):
        if n_clicks is None:
            return dash.no_update

        filtered_df = df_degrad[df_degrad["ESTADO"].isin(selected_states)]
        if remove_accents:
            filtered_df = filtered_df.applymap(
                lambda x: unidecode.unidecode(x) if isinstance(x, str) else x
            )

        return dcc.send_data_frame(
            filtered_df.to_csv,
            "desmatamento_assentamentos.csv",
            sep=decimal_separator,
            index=False,
        )

    # Retorna o app configurado ao Flask pai
    return app
