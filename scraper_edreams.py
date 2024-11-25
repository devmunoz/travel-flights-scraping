import argparse
import json
import locale
import os
import re
from datetime import datetime
from time import sleep

import numpy as np
import pandas as pd
import requests
import tqdm
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By


# Funcion principal del scrapeo a edreams. Gestiona todas las acciones necesarias para scrapear (selenium, diferentes urls, soap, preparar y devolver datos)
def scrapping_edreams(origen, inicio, fin):
    print(f"Procesando {origen} - {inicio} to {fin}")
    url = "https://www.edreams.es"

    # Llamada a la funcion que se encarga de hacer las acciones necesarias mediante selenium para lanzar la busquesda inicial por origen + fechas
    soup = obtener_posibles_destinos(url=url, origen=origen, inicio=inicio, fin=fin)

    # Generar las URLs de destinos+fechas basado en el contenido de la etiqueta article y la plantilla de url
    # "{url}/travel/#results/type=R;dep={inicio};from={origen};to={destino};ret={fin};collectionmethod=false"
    destinos = soup.find_all("article", class_="od-inspirational-grid-col")
    # obtenemos los codigos IATA sobre los que luego buscaremos al intruducirlos como parametros en la URL
    lista_destinos = [destino.find("figure")["data-iata"] for destino in destinos]

    urls_destinos = {}
    for destino in lista_destinos:
        # url_template = f"{url}/travel/#results/type=R;dep={inicio};from={origen};to={???};ret={fin};collectionmethod=false"
        urls_destinos[destino] = (
            f"{url}/travel/#results/type=R;dep={inicio};from={origen};to={destino};ret={fin};collectionmethod=false"
        )

    # scrap data
    datos_scrapeados = []
    for destino, destino_url in tqdm.tqdm(
        urls_destinos.items(), total=len(urls_destinos)
    ):
        # datos fijos que sabemos por la propia busqueda: url, origen, destino, inicio, fin
        fixed_data = [destino_url, origen, destino, inicio, fin]

        # datos obtenidos del scrapeo de la url con los vuelos a ese destino
        data_destino = datos_destino(url=destino_url)

        # list comprehension para nutrir cada elemento con los valores fijos
        full_data_destino = [fixed_data + rd for rd in data_destino]

        datos_scrapeados.extend(full_data_destino)

    return datos_scrapeados


# Funcion que realiza con selenium todas las acciones dinamicas para poder obtener todos los posibles destinos en base a un origen y unas fechas
def obtener_posibles_destinos(url, origen, inicio, fin):
    browser = webdriver.Chrome()
    browser.get(url)
    sleep(1)
    browser.maximize_window()
    sleep(1)

    try:
        # aceptar cookies
        browser.find_element(By.ID, "didomi-notice-agree-button").click()
        sleep(5)

        # Escribir en el inputo de origen el valor recibido
        browser.find_element(By.XPATH, '//input[@test-id="input-airport"]').send_keys(
            origen
        )
        sleep(5)

        # Click en el origen que se muestra como resultado del paso anterior
        browser.find_element(
            By.XPATH, '//div[@test-id="airport-departure"]'
        ).find_element(
            By.XPATH, f'.//ul/li/div/span[contains(text(), "{origen}")]'
        ).click()
        sleep(5)

        # Click en la primera opcion de destino que se muestra al hacer el paso anterior, que es cualquier destino
        browser.find_element(
            By.XPATH, '//div[@test-id="airport-destination"]'
        ).find_element(
            By.XPATH,
            './/div/div/ul/li/div[contains(@class, "odf-dropdown-col") and contains(@class, "lg") and contains(@class, "odf-text-nowrap")]',
        ).click()
        sleep(5)

        # Logica para abrir el calendario y elegir las fechas que hemos recibido, fecha de inicio
        div_calendario_salida = browser.find_element(
            By.XPATH, '//div[@data-testid="departure-date-picker"]'
        )
        procesar_calendario(fecha=inicio, element=div_calendario_salida)
        sleep(5)

        # Logica para abrir el calendario y elegir las fechas que hemos recibido, fecha de fin
        div_calendario_vuelta = browser.find_element(
            By.XPATH, '//div[@data-testid="return-date-picker"]'
        )
        procesar_calendario(fecha=fin, element=div_calendario_vuelta)
        sleep(5)

        # Click en el boton Continuar para confirmar las fechas (y todo lo previo)
        div_calendario_vuelta.find_element(
            By.XPATH, './/div/button[contains(text(), "Continuar")]'
        ).click()

        # Lanzar la busqueda de destinos
        boton_buscar = browser.find_element(
            By.XPATH, '//button[@test-id="search-flights-btn"]'
        )
        boton_buscar.click()
        sleep(10)

        # Una vez ha cargado los resultados, lo montamos en BS y lo devolvemos
        soup = BeautifulSoup(browser.page_source, "html.parser")
        browser.quit()

        if soup is None:
            raise Exception

        return soup

    except Exception as exception:
        print(f"Excepcion buscando destinos... {exception}")
        return None


# Funcion para parsear la fecha recibida a un formato especial que hay en la pagina
def custom_ano_mes_format(fecha=datetime.now()):
    locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
    # Obtener el nombre del mes en formato completo (por ejemplo, "noviembre")
    parsed_month = fecha.strftime("%B").capitalize()

    # Obtener los dos últimos dígitos del año (por ejemplo, "23" en lugar de "2023")
    parsed_year = fecha.strftime("%y")

    # Formatear la fecha en el formato deseado "Mes 'YY"
    formatted_fecha = f"{parsed_month} '{parsed_year}"

    return formatted_fecha


# Funcion para mostrar el mes deseado, via selenium
def mostrar_mes(ano_mes_str, html_element):
    while True:
        # Obtener los calendarios de los meses que actualmente vemos en la pagina
        meses_visibles = [
            e.text
            for e in html_element.find_elements(
                By.CSS_SELECTOR, "div.odf-calendar-title"
            )
        ]

        # Comprobamos si tenemos visible el mes que queremos
        if ano_mes_str in meses_visibles:
            # Si el mes que buscamos esta en pantalla, salimos
            break
        else:
            # Si no esta visible el mes, hacemos click en el boton de siguiente mes y volvemos al inicio del while
            html_element.find_element(
                By.XPATH,
                './/div/div/div/button/span[contains(@class, "odf-icon-arrow-right")]',
            ).click()

    return


# Funcion para procesar las acciones necesarias con selenium para mostrar el calendario
def procesar_calendario(fecha, element):
    # A partir de la fecha recibida, transformamos a formato "Mes 'YY" que es lo que la web muestra y por lo tanto hay que buscar
    fecha_datetime = datetime.strptime(fecha, "%Y-%m-%d")
    fecha_ano_mes = custom_ano_mes_format(fecha_datetime)

    # La pagina nos muestra 2 meses, el actual y el siguiente, pero debemos buscar realmente el que corresponda a la fecha recibida
    mostrar_mes(ano_mes_str=fecha_ano_mes, html_element=element)

    # Una vez tenemos visible el mes que queremos, buscamos el mes
    calendario_fecha = element.find_element(
        By.XPATH,
        f'.//div[contains(@class, "odf-calendar-title") and contains(text(), "{fecha_ano_mes}")]/following-sibling::div',
    )

    # Buscamos el dia dentro de ese mes, y le hacemos click
    dia_fecha = calendario_fecha.find_element(
        By.XPATH,
        f'.//div[contains(@class, "odf-calendar-day") and contains(text(), "{fecha_datetime.day}")]',
    )

    # Le hacemos click
    dia_fecha.click()


# Funcion para detectar y quitar una alerta/boton molesto
def check_boton_molesto(browser):
    # check stupid alert
    try:
        stupid_alert = browser.find_element(By.ID, "sessionAboutToExpireAlert")

        if stupid_alert:
            stupid_button = stupid_alert.find_element(By.CCS_SELECTOR, "button")
            if stupid_button:
                stupid_button.click()
                sleep(1)
                return True
    except Exception:
        # print("Error detectando el boton estupido...")
        return False

    return False


# Funcion para scrapear con selenuim y BS el detalle de los vuelos segun la url recibida que contiene ya el conjunto de datos de origen, destino, inicio y fin
def datos_destino(url):
    print(f"Processing {url}")
    lista_datos_destino = []

    browser = webdriver.Chrome()
    browser.get(url)
    sleep(1)
    browser.maximize_window()
    sleep(15)

    # Aceptar cookies
    browser.find_element(By.ID, "didomi-notice-agree-button").click()
    sleep(1)

    # Bucle para hacer scroll y clieck en mostrar mas resultados, hasta que no se pueda hacer mas scroll
    counter = 0
    scroll = 10000
    while True:
        # Scroll
        browser.execute_script(f"window.scrollBy(0, {scroll});")
        sleep(6)
        # Checkeamos si existe un boton molesto, y lo quitamos
        check_boton_molesto(browser=browser)

        # Buscamos los botones
        botones = browser.find_element(By.ID, "results_list_container").find_elements(
            By.XPATH, ".//button"
        )

        # Si hay botones y el ultimo boton contiene "Mostrar ", le damos click
        if len(botones) and botones[-1] and "Mostrar " in botones[-1].text:
            # print("Click en " + botones[-1].text)
            try:
                botones[-1].click()
            except Exception:
                # En caso de error, checkeamos si existe el boton molesto, y lo quitamos
                if check_boton_molesto(browser=browser):
                    print("Boton estupido detectado y clickado :)")
                    continue
                else:
                    # Si hay error desconocido, simplemente dejamos de hacer scroll y pasamos a extraer datos
                    break

            counter += 1
            # Cada bucle aumentamos el scroll
            scroll += 500

        elif not check_boton_molesto(browser=browser):
            # Si no tengo botones ni boton molesto, dejo de hacer scroll
            break

    sleep(4)
    print(f"Scroll hecho {counter} veces")

    # Montamos el BS con el contenido
    soup = BeautifulSoup(browser.page_source, "html.parser")
    browser.quit()

    # Contenedor con todos los divs de vuelos
    results_container = soup.find(id="results_list_container")
    elements = results_container.find_all(attrs={"data-testid": "itinerary"})

    for element in elements:
        duraciones = []
        escalas = []
        datos_horas = []
        equipajes = []

        try:
            # Aeropuertos, es una lista con los 2 de la ida y los 2 de la vuelta
            aeropuertos = element.find_all("div", {"type": "small"})
            aeropuertos_data = [
                aeropuertos[0].text.strip(),
                aeropuertos[2].text.strip(),
                aeropuertos[4].text.strip(),
                aeropuertos[6].text.strip(),
            ]

            # Aerolineas, las dejamos en una lista de valores unicos
            aerolineas_elem = element.find_all("img")
            aerolineas = list(
                {a.attrs["alt"] for a in aerolineas_elem if "alt" in a.attrs}
            )

            # Precios. El bueno es el unit_price, pero tambien hay otros precios con descuento que pueden servir
            price_spans = element.find_all("span", class_="money-integer")
            prices = [p.text for p in price_spans]
            unit_price = element.select("a > span > span.money-integer")[0].text

            # Variable para tener todos los divs del vuelo
            divs_vuelo = element.find_all("div")

            # Bucle para iterar por todos los divs y sacar los diferentes datos
            for div_item in divs_vuelo:
                # Logica para sacar las horas de despegue y llegada
                if len(div_item.attrs) == 1 and "class" in div_item.attrs:
                    # Al ser clases css dinamicas, hay que recorrerlas y buscar la que acabe en BaseText-Body que es estatico.
                    for attr_class in div_item.attrs["class"]:
                        # Regex para buscar en el contenido del div que tenga un formato de XX:XX
                        if attr_class.endswith("BaseText-Body") and re.match(
                            r"^\d{2}:\d{2}$", div_item.text.strip()
                        ):
                            datos_horas.append(div_item.text)
                # Logica para sacar datos de escalas, a partir de un atributo orientation que tiene ese elemento
                elif len(div_item.attrs) > 1 and "orientation" in div_item.attrs:
                    # Es imposible detectar directamente el elemento, por eso buscamos el anterior que si podemos encontrar, y vamos al siguiente sibling
                    next_sibling = div_item.findNextSibling()
                    if next_sibling:
                        # El span contiene las duraciones y las escalas
                        span_items = next_sibling.find_all("span")
                        duraciones.append(span_items[0].text)
                        escalas.append(
                            span_items[1].text if len(span_items) > 1 else "0"
                        )

            # Bucle para iterar por todos los elementos path y sacar datos
            child_paths = element.find_all("path")
            for path_item in child_paths:
                # clip-rule es algo fijo que siempre podremos encontrar
                if len(path_item.attrs) > 1 and "clip-rule" in path_item.attrs:
                    # ojo sensibles: buscamos tres veces el parent
                    tri_parent = path_item.parent.parent.parent
                    if tri_parent:
                        # buscamos el siguiente elemento
                        equipaje_div = tri_parent.findNextSibling()
                        if equipaje_div:
                            # agregamos la info de maletas
                            equipajes.append(equipaje_div.text)

        except Exception as exception:
            print(f"Ignorando vuelo por problemas al scrapear...{exception}")
            continue

        lista_datos_destino.append(
            [
                aeropuertos_data,
                aerolineas,
                datos_horas,
                duraciones,
                escalas,
                equipajes,
                unit_price,
                prices,
            ]
        )

    return lista_datos_destino


AIRTABLE_BASE_URL = os.getenv("AIRTABLE_BASE_URL")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE_ID = os.getenv("AIRTABLE_TABLE_ID")
API_KEY = os.getenv("AIRTABLE_API_KEY_SHARED")


# Funcion para subir a airtables el df
def subir_datos_airtable(df):
    API_KEY = os.getenv(
        "AIRTABLE_API_KEY_SHARED"
    )  # API KEY de AirTable cargada desde el ordenador mediante un fichero .env

    # Headers - Credenciales para hacer solicitudes mediante API en AirTable
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    # Formateos para evitar errores
    df1 = df.replace({"": None})
    df1 = df1.replace({np.nan: None})

    datos_df = []

    for idx, row in df1.iterrows():
        data = {"fields": row.to_dict()}
        datos_df.append(data)

    # endpoint
    endpoint = f"{AIRTABLE_BASE_URL}/{BASE_ID}/{TABLE_ID}"

    counter = 0
    while counter < len(datos_df):
        datos_subir = datos_df[counter : counter + 10]
        datos_subir = {"records": datos_subir, "typecast": True}

        response = requests.post(url=endpoint, json=datos_subir, headers=headers)

        (f"response: {response.status_code}")
        # print(f"endpoint: {response.url}")
        # print("-"*120)
        counter += 10
        sleep(1)

    print(f"Subidos {len(datos_df)} registros a airtables")


# Funcion para crear el df con los datos scrapeados de edreams
def crear_df(data):
    columnas_df = [
        "url",
        "origen",
        "destino",
        "fecha_inicio",
        "fecha_fin",
        "pasajeros",
        "inicio_ida",
        "fin_ida",
        "inicio_vuelta",
        "fin_vuelta",
        "escala_ida",
        "escala_vuelta",
        "duracion_ida",
        "duracion_vuelta",
        "aerolineas",
        "equipaje_mano",
        "equipaje_bodega",
        "precio",
        "clase",
    ]
    df = pd.DataFrame(data, columns=columnas_df)

    # Ajusta las columnas de escalas para que sea solo el numero. De origen viene directo o X escalas
    df["escala_ida"] = df.apply(
        lambda row: int(row["escala_ida"][:1] if row["escala_ida"] != "directo" else 0),
        axis=1,
    )
    df["escala_vuelta"] = df.apply(
        lambda row: int(
            row["escala_vuelta"][:1] if row["escala_vuelta"] != "directo" else 0
        ),
        axis=1,
    )

    # Ajusta las columnas de duracion para que el formato sea 1h 35m en vez de 1 h 35 min
    df["duracion_ida"] = df.apply(
        lambda row: row["duracion_ida"].replace(" h", "h").replace(" min", "m"), axis=1
    )
    df["duracion_vuelta"] = df.apply(
        lambda row: row["duracion_vuelta"].replace(" h", "h").replace(" min", "m"),
        axis=1,
    )

    # guardar en pkl el df con un timestamp
    now = datetime.now()
    now_timestamp = now.strftime("%Y%m%d%H%M%S")
    file_name = f"edreams_data_{now_timestamp}"
    df.to_pickle(f"{file_name}.pkl")
    print(f"Creado {file_name}.pkl")  ## Ejecución del proceso

    return df


IATA_CODES_URL = "https://raw.githubusercontent.com/ip2location/ip2location-iata-icao/refs/heads/master/iata-icao.csv"


def cargar_codigos_iata_desde_url():
    """
    Descarga y carga los códigos IATA desde una URL de archivo CSV.
    :param url: URL del archivo CSV.
    :return: Conjunto de códigos IATA válidos.
    """
    try:
        # Leer el CSV directamente desde el contenido descargado
        df = pd.read_csv(IATA_CODES_URL)

        # Obtener la columna "iata_code" y convertirla en un conjunto
        codigos_iata = set(df["iata"].dropna().str.upper())
        return codigos_iata
    except Exception as e:
        print(f"Error al cargar el archivo CSV desde la URL: {e}")
        exit(1)


def validar_codigos_iata(codigos, codigos_validos):
    """
    Valida una lista de códigos IATA contra una lista de códigos válidos.
    :param codigos: Lista de códigos a validar.
    :param codigos_validos: Conjunto de códigos IATA válidos.
    :return: Diccionario con los resultados de la validación.
    """

    resultados = {
        "ok": list(),
        "nok": list(),
    }
    for codigo in codigos:
        if codigo in codigos_validos:
            resultados["ok"].append(codigo)
        else:
            resultados["nok"].append(codigo)
    return resultados


# scraping process #
def scrap(fechas, origenes):
    # Bucle para recorrer cada uno de los origenes
    for origen in origenes:
        # Bucle para recorrer cada una de las fechas
        for date in fechas:
            data = []
            # Llamada a la funcion que, en base al origen + fechas, lanza todo el scrapeo necesario y nos devuelve una lista de valores
            lista_datos_obtenidos = scrapping_edreams(
                origen=origen, inicio=date["from"], fin=date["to"]
            )

            # Bucle para recopilar los datos obtenidos del scrapeo, setear algunos datos fijos, parsear y tener el conjunto de datos finales para generar el df
            for datos_obtenidos in lista_datos_obtenidos:
                url = datos_obtenidos[0]
                origen = datos_obtenidos[1]
                destino = datos_obtenidos[2]
                fecha_inicio = datos_obtenidos[3]
                fecha_fin = datos_obtenidos[4]
                pasajeros = 1  # valor fijo
                inicio_ida = datos_obtenidos[7][0]
                fin_ida = datos_obtenidos[7][1]
                inicio_vuelta = datos_obtenidos[7][2]
                fin_vuelta = datos_obtenidos[7][3]
                escala_ida = datos_obtenidos[9][0]
                escala_vuelta = datos_obtenidos[9][1]
                duracion_ida = datos_obtenidos[8][0]
                duracion_vuelta = datos_obtenidos[8][1]
                aerolineas = datos_obtenidos[6]
                equipaje_mano_value = (
                    datos_obtenidos[10][0] if len(datos_obtenidos[10]) > 1 else ""
                )  # En edreams solo podemos detectar equipaje de mano, buscamos ese valor y sino 0
                equipaje_mano = 1 if equipaje_mano_value == "Equipaje de mano" else 0
                equipaje_bodega = 0  # no existe este valor en edreams
                precio = datos_obtenidos[11]
                clase = None  # no existe este valor en edreams

                data.append(
                    [
                        url,
                        origen,
                        destino,
                        fecha_inicio,
                        fecha_fin,
                        pasajeros,
                        inicio_ida,
                        fin_ida,
                        inicio_vuelta,
                        fin_vuelta,
                        escala_ida,
                        escala_vuelta,
                        duracion_ida,
                        duracion_vuelta,
                        aerolineas,
                        equipaje_mano,
                        equipaje_bodega,
                        precio,
                        clase,
                    ]
                )

            if len(data) > 0:
                # Creamos el df
                data_df = crear_df(data=data)
                # Subimos el df a airtables
                # subir_datos_airtable(df=data_df)
                print(data_df)
        print("===================== FIN DEL PROCESO =====================")


if __name__ == "__main__":
    # Configuración de argparse para recibir argumentos desde la línea de comandos
    parser = argparse.ArgumentParser(description="eDreams flights scraping script")

    # Parámetro para las fechas como un JSON string
    parser.add_argument(
        "--dates",
        type=str,
        required=True,
        help='Input dates dict (JSON). Example: \'[{"from": "2024-12-06", "to": "2025-01-10"}]\'',
    )

    # Parámetro para los destinos
    parser.add_argument(
        "--sources",
        type=str,
        required=True,
        help='Input sources list, IATA codes (JSON). Example: \'["MAD","VLC","BCN"]\'',
    )

    args = parser.parse_args()

    # Convertir el argumento JSON a lista/diccionario
    fechas = json.loads(args.dates)
    origenes = json.loads(args.sources)

    # Cargar códigos válidos desde la URL
    codigos_validos = cargar_codigos_iata_desde_url()

    # Validar los códigos proporcionados
    resultados = validar_codigos_iata(origenes, codigos_validos)

    if len(resultados["ok"]) == 0:
        print(
            "No se han introducido códigos IATA válidos. Ejecute el script get_iata_codes.py para obtener la lista de codigos válidos"
        )
        exit(1)

    if len(resultados["nok"]) > 0:
        print(
            f"Algunos origenes serán ignorados por no ser un código IATA válido: {', '.join(resultados['nok'])}"
        )

    # Llamar al proceso de scraping con las fechas proporcionadas
    scrap(fechas=fechas, origenes=origenes)
