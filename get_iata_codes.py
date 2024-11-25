import pandas as pd

IATA_CODES_URL = "https://raw.githubusercontent.com/ip2location/ip2location-iata-icao/refs/heads/master/iata-icao.csv"

try:
    df = pd.read_csv(IATA_CODES_URL)
    df = df[["iata", "airport"]]
    df.dropna(inplace=True)
    df.set_index("iata", inplace=True)
    df.sort_values(by="iata", inplace=True)

    print(df.to_string())

except Exception as e:
    print(f"Error al cargar el archivo CSV desde la URL: {e}")
    exit(1)
