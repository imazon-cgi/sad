import os
import pandas as pd
import geopandas as gpd
import pyarrow
import fastparquet

# Função para converter CSV para Parquet
def csv_to_parquet(input_folder, output_folder):
    # Cria a pasta de destino, caso não exista
    os.makedirs(output_folder, exist_ok=True)
    
    # Itera sobre os arquivos dentro do diretório de entrada
    for file_name in os.listdir(input_folder):
        if file_name.lower().endswith('.csv'):
            # Caminhos completo de entrada e saída
            input_path = os.path.join(input_folder, file_name)
            output_file_name = os.path.splitext(file_name)[0] + '.parquet'
            output_path = os.path.join(output_folder, output_file_name)

            try:
                # Lê o CSV com pandas
                df = pd.read_csv(input_path)

                # Salva em formato Parquet
                df.to_parquet(output_path, index=False)
                print(f"Convertido CSV -> Parquet: {output_path}")
            except Exception as e:
                print(f"Erro ao converter {file_name} para Parquet: {e}")

# Função para simplificar e converter GeoJSON
def simplify_geojson(input_folder, output_folder, tolerancia=0.01):
    # Cria a pasta de destino, caso não exista
    os.makedirs(output_folder, exist_ok=True)

    # Itera sobre os arquivos dentro do diretório de entrada
    for file_name in os.listdir(input_folder):
        if file_name.lower().endswith('.geojson'):
            # Caminhos completo de entrada e saída
            input_path = os.path.join(input_folder, file_name)
            output_path = os.path.join(output_folder, file_name)

            try:
                # Lê o GeoJSON com geopandas
                gdf = gpd.read_file(input_path)

                # Verificar o CRS original
                print(f"Arquivo: {file_name} - CRS Original: {gdf.crs}")

                # Se não tiver CRS definido, definir manualmente como WGS84
                if gdf.crs is None:
                    gdf.set_crs(epsg=4326, inplace=True)
                    print(f"Arquivo: {file_name} - CRS Definido Manualmente: EPSG:4326")

                # Se o CRS não for EPSG:4674, converter
                if gdf.crs.to_string() != 'EPSG:4674':
                    gdf = gdf.to_crs(epsg=4674)
                    print(f"Arquivo: {file_name} - Convertido para: EPSG:4674")

                # Simplifica a geometria mantendo a topologia
                gdf['geometry'] = gdf['geometry'].simplify(
                    tolerance=tolerancia, 
                    preserve_topology=True
                )

                # Salva o GeoJSON resultante
                gdf.to_file(output_path, driver='GeoJSON')
                print(f"Simplificado e salvo GeoJSON: {output_path}")

            except Exception as e:
                print(f"Erro ao processar {file_name}: {e}")

if __name__ == "__main__":
    # Caminhos específicos fornecidos
    csv_input_folder = r'F:\VSCode\13 - MUNDO\sad\database\csv'
    csv_output_folder = r'F:\VSCode\13 - MUNDO\sad\sad\datasets\csv'
    geojson_input_folder = r'F:\VSCode\13 - MUNDO\sad\database\geojson'
    geojson_output_folder = r'F:\VSCode\13 - MUNDO\sad\sad\datasets\geojson'

    # Converte CSV para Parquet
    csv_to_parquet(csv_input_folder, csv_output_folder)

    # Simplifica e ajusta CRS de arquivos GeoJSON
    simplify_geojson(
        input_folder=geojson_input_folder,
        output_folder=geojson_output_folder,
        tolerancia=0.01
    )
