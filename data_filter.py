import os
import pandas as pd
import geopandas as gpd
import pyarrow
import fastparquet


def csv_to_parquet(input_folder='database/csv', output_folder='datasets/csv'):
    # Cria a pasta de destino, caso não exista
    os.makedirs(output_folder, exist_ok=True)
    
    # Itera sobre os arquivos dentro de input_folder
    for file_name in os.listdir(input_folder):
        if file_name.lower().endswith('.csv'):
            # Caminhos completo de entrada e saída
            input_path = os.path.join(input_folder, file_name)
            output_file_name = os.path.splitext(file_name)[0] + '.parquet'
            output_path = os.path.join(output_folder, output_file_name)

            # Lê o CSV com pandas
            df = pd.read_csv(input_path)

            # Salva em formato Parquet
            df.to_parquet(output_path, index=False)
            print(f"Convertido CSV -> Parquet: {output_path}")

def simplify_geojson(
    input_folder='database/geojson', 
    output_folder='datasets/geojson', 
    tolerancia=0.01
):
    # Cria a pasta de destino, caso não exista
    os.makedirs(output_folder, exist_ok=True)

    # Itera sobre os arquivos dentro de input_folder
    for file_name in os.listdir(input_folder):
        if file_name.lower().endswith('.geojson'):
            # Caminhos completo de entrada e saída
            input_path = os.path.join(input_folder, file_name)
            output_path = os.path.join(output_folder, file_name)

            # Lê o GeoJSON com geopandas
            gdf = gpd.read_file(input_path)

            # Simplifica a geometria mantendo a topologia
            gdf['geometry'] = gdf['geometry'].simplify(
                tolerance=tolerancia, 
                preserve_topology=True
            )

            # Converte o CRS para EPSG:4674
            gdf = gdf.to_crs(epsg=4674)

            # Salva o GeoJSON resultante
            gdf.to_file(output_path, driver='GeoJSON')
            print(f"Simplificado e salvo GeoJSON: {output_path}")

if __name__ == "__main__":
    # Converte CSV para Parquet
    csv_to_parquet('database/csv', 'datasets/csv')

    # Simplifica e ajusta CRS de arquivos GeoJSON
    simplify_geojson(
        input_folder='database/geojson',
        output_folder='datasets/geojson',
        tolerancia=0.01
    )