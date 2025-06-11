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


# -----------------------------------------------------------------------------
def register_sad_degradacao_uc(server):
    """Acopla o dashboard de UC a um servidor Flask já existente."""
    external_css = [
        dbc.themes.BOOTSTRAP,
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css",
    ]

    app = dash.Dash(
        __name__,
        server=server,
        url_base_pathname="/sad/degradacao_uc/",
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

    def load_csv(url: str):
        # na verdade é Parquet; mantido para compatibilidade
        return pd.read_parquet(url)

    # ---------------------------------------------------------------- dados
    brazil_states = load_geojson(
        "https://github.com/imazon-cgi/sad/raw/refs/heads/main/datasets/geojson/AMZ_unidade_conservacao.geojson"
    )
    df_degrad = load_csv(
        "https://github.com/imazon-cgi/sad/raw/refs/heads/main/datasets/csv/alertas_sad_degradacao_09_2008_04_2024_unidadeConservacao.parquet"
    )

    list_states = df_degrad["ESTADO"].unique()
    list_anual: List[int] = sorted(df_degrad["ANO"].unique())
    state_options = [{"label": s, "value": s} for s in list_states]

    # ---------------------------------------------------------------- layout
    app.layout = dbc.Container(
        [
            html.Meta(name="viewport", content="width=device-width, initial-scale=1"),
            # topo sem título H1
            dbc.Row(
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            dbc.Button(
                                                [
                                                    html.I(className="fa fa-filter mr-1"),
                                                    "Remover Filtros",
                                                ],
                                                id="reset-button-top",
                                                n_clicks=0,
                                                color="success",
                                                className="btn-sm custom-button",
                                            ),
                                            width="auto",
                                            className="d-flex justify-content-end",
                                        ),
                                        dbc.Col(
                                            dbc.Button(
                                                [
                                                    html.I(className="fa fa-map mr-1"),
                                                    "Selecione o Estado",
                                                ],
                                                id="open-state-modal-button",
                                                color="success",
                                                className="btn-sm custom-button",
                                            ),
                                            width="auto",
                                            className="d-flex justify-content-end",
                                        ),
                                        dbc.Col(
                                            dbc.Button(
                                                [
                                                    html.I(className="fa fa-download mr-1"),
                                                    "Baixar CSV",
                                                ],
                                                id="open-modal-button",
                                                color="success",
                                                className="btn-sm custom-button",
                                            ),
                                            width="auto",
                                            className="d-flex justify-content-end",
                                        ),
                                    ],
                                    justify="end",
                                ),
                                dcc.Download(id="download-dataframe-csv"),
                            ]
                        ),
                        className="mb-4 title-card",
                    ),
                    width=12,
                )
            ),
            # gráficos principais
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(dcc.Graph(id="bar-graph-total", config={"responsive": True}), className="graph-block"),
                        width=12,
                        lg=6,
                    ),
                    dbc.Col(
                        dbc.Card(dcc.Graph(id="bar-graph-yearly", config={"responsive": True}), className="graph-block"),
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
                        dbc.Card(dcc.Graph(id="line-graph", config={"responsive": True}), className="graph-block"),
                        width=12,
                        lg=6,
                    ),
                    dbc.Col(
                        dbc.Card(dcc.Graph(id="choropleth-map", config={"responsive": True}), className="graph-block"),
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
                            min=int(min(list_anual)),
                            max=int(max(list_anual)),
                            value=int(max(list_anual)),
                            marks={
                                str(y): {"label": str(y), "style": {"transform": "rotate(-45deg)", "margin-top": "15px"}} for y in list_anual
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
            # dois gráficos de pizza
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(dcc.Graph(id="pie-graph-uso", config={"responsive": True}), className="graph-block"),
                        width=12,
                        lg=6,
                    ),
                    dbc.Col(
                        dbc.Card(dcc.Graph(id="pie-graph-unid-conse", config={"responsive": True}), className="graph-block"),
                        width=12,
                        lg=6,
                    ),
                ],
                className="mb-4",
                style={"border": "none"},
            ),
            dcc.Store(id="selected-states", data=[]),
            # modal seleção estado (dropdown) e download (sem alterações nos modais)
            dbc.Modal(...),
            dbc.Modal(...),
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
            Output("pie-graph-uso", "figure"),
            Output("pie-graph-unid-conse", "figure"),
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
        # ------------- controle de cliques / filtros -------------------
        triggered_id = [p["prop_id"] for p in callback_context.triggered][0]

        if triggered_id == "reset-button-top.n_clicks":
            selected_states = []
            selected_state = []
            selected_year = int(max(list_anual))
        else:
            if triggered_id == "choropleth-map.clickData" and map_click_data:
                muni = map_click_data["points"][0]["location"]
                selected_states = (
                    [s for s in selected_states if s != muni]
                    if muni in selected_states
                    else selected_states + [muni]
                )
            if triggered_id == "bar-graph-yearly.clickData" and bar_click_data:
                muni = bar_click_data["points"][0]["y"]
                selected_states = (
                    [s for s in selected_states if s != muni]
                    if muni in selected_states
                    else selected_states + [muni]
                )
            if triggered_id == "bar-graph-total.clickData" and total_bar_click_data:
                selected_year = total_bar_click_data["points"][0]["x"]

        if not selected_state:
            selected_state = []

        # ------------- pré-processamento ---------------------------------
        df_acumulado_ano = (
            df_degrad.groupby(["ESTADO", "ANO"])["AREAKM2"].sum().reset_index()
        )
        df_acumulado_ano["AREAKM2"] = df_acumulado_ano["AREAKM2"].round(2)
        df_acumulado_ano["ANO"] = df_acumulado_ano["ANO"].astype(int)
        df_acumulado_ano["PERCENTUAL"] = df_acumulado_ano.groupby("ANO")[
            "AREAKM2"
        ].transform(lambda x: (x / x.sum()) * 100)
        df_acumulado_ano["PERCENTUAL"] = df_acumulado_ano["PERCENTUAL"].round(2)

        df_acumulado_ano_uc = (
            df_degrad.groupby(["UNID_CONSE", "ESTADO", "ANO"])["AREAKM2"]
            .sum()
            .reset_index()
        )
        df_acumulado_ano_uc["AREAKM2"] = df_acumulado_ano_uc["AREAKM2"].round(2)
        df_acumulado_ano_uc["ANO"] = df_acumulado_ano_uc["ANO"].astype(int)
        df_acumulado_ano_uc["PERCENTUAL"] = df_acumulado_ano_uc.groupby("ANO")[
            "AREAKM2"
        ].transform(lambda x: (x / x.sum()) * 100)
        df_acumulado_ano_uc["PERCENTUAL"] = df_acumulado_ano_uc["PERCENTUAL"].round(2)

        # ------------- barra horizontal top-15 ---------------------------
        if selected_state:
            df_year = (
                df_acumulado_ano_uc[
                    (df_acumulado_ano_uc["ANO"] == selected_year)
                    & (df_acumulado_ano_uc["ESTADO"].isin(selected_state))
                ]
                .sort_values(by="AREAKM2", ascending=False)
                .head(15)
            )
        else:
            df_year = (
                df_acumulado_ano_uc[df_acumulado_ano_uc["ANO"] == selected_year]
                .sort_values(by="AREAKM2", ascending=False)
                .head(15)
            )

        bar_yearly_fig = go.Figure(
            go.Bar(
                y=df_year["UNID_CONSE"],
                x=df_year["AREAKM2"],
                orientation="h",
                marker_color=[
                    "green" if u in selected_states else "DarkSeaGreen"
                    for u in df_year["UNID_CONSE"]
                ],
                text=[
                    f"{v} km² ({p}%)"
                    for v, p in zip(df_year["AREAKM2"], df_year["PERCENTUAL"])
                ],
                textposition="auto",
            )
        )
        bar_yearly_fig.update_yaxes(autorange="reversed")
        bar_yearly_fig.update_layout(
            xaxis_title="Área (km²)",
            yaxis_title="Unidades de Conservação",
            bargap=0.1,
            font=dict(size=10),
            title=dict(
                text=(
                    f"SAD Alertas de Degradação Florestal Acumulado <br>Unidades de Conservação ({selected_year})"
                    if not selected_state
                    else f"SAD Alertas de Degradação Florestal Acumulado <br>Unidades de Conservação ({', '.join(selected_state)}) ({selected_year})"
                ),
                x=0.5,
            ),
        )

        # ------------- mapa ---------------------------------------------
        df_map = df_year[df_year["UNID_CONSE"].isin(selected_states)] if selected_states else df_year
        map_fig = px.choropleth_mapbox(
            df_map,
            geojson=brazil_states,
            color="AREAKM2",
            locations="UNID_CONSE",
            featureidkey="properties.nome_uc",
            mapbox_style="open-street-map",
            center={"lat": -14, "lon": -55},
            color_continuous_scale="YlOrRd",
            zoom=3,
        )
        map_fig.update_layout(
            title=dict(
                text=f"Mapa de Degradação Ambiental (km²) - {selected_year}",
                x=0.5,
                font={"size": 14},
            ),
            margin={"r": 0, "t": 50, "l": 0, "b": 0},
            mapbox={"zoom": 3, "center": {"lat": -14, "lon": -55}},
        )

        # ------------- linha temporal -----------------------------------
        if selected_state:
            df_line = df_acumulado_ano_uc[
                df_acumulado_ano_uc["ESTADO"].isin(selected_state)
            ]
            line_title = (
                f"SAD Alertas de Degradação Florestal Acumulado<br>"
                f"Unidades de Conservação por Estado ({', '.join(selected_state)})"
            )
        else:
            df_line = df_acumulado_ano_uc.copy()
            line_title = (
                "SAD Alertas de Degradação Florestal Acumulado - Unidades de Conservação por Estado"
            )

        line_fig = px.line(
            df_line,
            x="ANO",
            y="AREAKM2",
            color="UNID_CONSE",
            title=line_title,
            labels={"AREAKM2": "Área (km²)", "ANO": "Ano"},
            template="plotly_white",
            line_shape="spline",
            color_discrete_sequence=px.colors.sequential.Reds,
        )
        line_fig.update_traces(mode="lines+markers")
        line_fig.update_layout(
            xaxis_title="Ano",
            yaxis_title="Área (km²)",
            font=dict(size=10),
            yaxis=dict(tickformat=".0f"),
            legend=dict(itemsizing="constant"),
            title=dict(text=line_title, x=0.5),
        )

        # ------------- barra total anual --------------------------------
        df_filtered = (
            df_degrad[df_degrad["ESTADO"].isin(selected_state)]
            if selected_state
            else df_degrad.copy()
        )
        if selected_states:
            df_filtered = df_filtered[df_filtered["UNID_CONSE"].isin(selected_states)]

        df_degrad_accum_total = df_filtered.groupby("ANO")["AREAKM2"].sum().reset_index()
        df_degrad_accum_total["AREAKM2"] = df_degrad_accum_total["AREAKM2"].round(2)
        df_degrad_accum_total["ANO"] = df_degrad_accum_total["ANO"].astype(int)

        if selected_state and selected_states:
            title_text = (
                "SAD Alertas de Degradação Florestal Acumulado <br>"
                f"Unidades de Conservação ({', '.join(selected_states)}) ({', '.join(selected_state)})"
            )
        elif selected_state:
            title_text = (
                "SAD Alertas de Degradação Florestal Acumulado <br>"
                f"Unidades de Conservação ({', '.join(selected_state)})"
            )
        elif selected_states:
            title_text = (
                "SAD Alertas de Degradação Florestal Acumulado <br>"
                f"Unidades de Conservação ({', '.join(selected_states)})"
            )
        else:
            title_text = "SAD Alertas de Degradação Florestal Acumulado  - Amazônia Legal"

        bar_total_fig = px.bar(
            df_degrad_accum_total,
            x="ANO",
            y="AREAKM2",
            text="AREAKM2",
            title=title_text,
            labels={"AREAKM2": "Área (km²)", "ANO": "Ano"},
            template="plotly_white",
        )
        bar_total_fig.update_traces(
            marker_color="orange",
            marker_line_color="orange",
            marker_line_width=1.5,
            opacity=0.6,
            texttemplate="%{text:.2s}",
            textangle=-45,
            textposition="outside",
            textfont=dict(size=12, color="black", family="Arial"),
        )
        bar_total_fig.update_layout(
            title=dict(text=title_text, x=0.5),
            xaxis=dict(
                title="Ano",
                tickmode="linear",
                tickangle=-45,
                title_font=dict(size=10),
                tickfont=dict(size=10),
            ),
            yaxis=dict(
                title="Área (km²)",
                title_font=dict(size=10),
                tickfont=dict(size=10),
            ),
            font=dict(size=10),
            autosize=True,
        )

        # ------------- gráficos de pizza --------------------------------
        if selected_state:
            df_uso = df_degrad[
                (df_degrad["ANO"] == selected_year)
                & (df_degrad["ESTADO"].isin(selected_state))
            ].copy()
            df_uc_pie = df_uso.copy()
        else:
            df_uso = df_degrad[df_degrad["ANO"] == selected_year].copy()
            df_uc_pie = df_uso.copy()

        df_uso = (
            df_uso.groupby(["USO", "JURISDICAO"])["AREAKM2"]
            .sum()
            .reset_index()
            .nlargest(10, "AREAKM2")
        )
        df_uc_pie = (
            df_uc_pie.groupby(["UNID_CONSE", "USO"])["AREAKM2"]
            .sum()
            .reset_index()
            .nlargest(10, "AREAKM2")
        )

        pie_colors = px.colors.qualitative.Plotly

        pie_uso_fig = px.pie(
            df_uso,
            values="AREAKM2",
            names="USO",
            color="JURISDICAO",
            title="Área Degradada por<br>Tipo de Uso e Jurisdição",
        )
        pie_uso_fig.update_traces(
            textinfo="percent+label",
            marker=dict(colors=pie_colors),
            textfont=dict(size=8),
        )
        pie_uso_fig.update_layout(
            title_font=dict(size=12),
            legend=dict(
                font=dict(size=8),
                orientation="v",
                yanchor="top",
                y=1.1,
                xanchor="left",
                x=1.1,
                itemwidth=30,
                itemsizing="constant",
            ),
        )

        pie_uc_fig = px.pie(
            df_uc_pie,
            values="AREAKM2",
            names="UNID_CONSE",
            color="USO",
            title="Área Degradada por<br>Unidade de Conservação e Uso",
        )
        pie_uc_fig.update_traces(
            textinfo="percent+label",
            marker=dict(colors=pie_colors),
            textfont=dict(size=8),
        )
        pie_uc_fig.update_layout(
            title_font=dict(size=12),
            legend=dict(
                font=dict(size=8),
                orientation="v",
                yanchor="top",
                y=1.1,
                xanchor="left",
                x=1.1,
                itemwidth=30,
                itemsizing="constant",
            ),
        )

        # retorno
        return (
            bar_total_fig,
            bar_yearly_fig,
            map_fig,
            line_fig,
            pie_uso_fig,
            pie_uc_fig,
            selected_states,
            selected_state,
            selected_year,
        )

    # ---------------------------------------------------------------- modais e download
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
            "degradacao_amazonia.csv",
            sep=decimal_separator,
            index=False,
        )

    # Flask “pai” faz o run; aqui só retornamos
    return app
