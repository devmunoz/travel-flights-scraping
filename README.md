# eDreams Web Scraping 🛫🤑

###### Last update: 12/2024

#### Web Scraping and Data Collection Project

## Disclaimer

The script may not work properly in the future due to updates on the target page [eDreams](https://www.edreams.es). Keep in mind that web scraping is a technique that requires constant updates, and this project will not be maintained. This source code is for educational purposes only.

## Description

This repository is part of the original project performed by [José Dos Reis - josedosr](https://github.com/josedosr), [Pamela Colman - pamve](https://github.com/pamve) and me.

If you want more information, please check the original project [here](https://github.com/josedosr/flight_tickets_ETL).

This script can search and collect data from the eDreams search engine based on the provided dates and locations. The collected data can be processed using pandas or similar libraries.

## Demo Video

[See the demo video](https://github.com/devmunoz/travel-flights-scraping/raw/refs/heads/master/demo_scraping.mp4)

## Installation and Execution

- **Prerequisites**:
  - Install [Python](https://www.python.org/downloads/) and [Virtual Environment (venv)](https://docs.python.org/3/library/venv.html) on your machine.
  - Clone this repository.

- **Perform the scraping**:
  - Install the virtual environment:

    ```
    python -m venv .venv
    ```
  - Run the virtual environment:

    ```
    source .venv/bin/activate
    ```
  - Install the requirements:

    ```
    pip install -r requirements.txt
    ```
  - **Usage** 😄:

    ```
    usage: scraper_edreams.py [-h] --dates DATES --sources SOURCES

    eDreams flights scraping script

    options:
    -h, --help         show this help message and exit
    --dates DATES      Input dates dict (JSON). Example: '[{"from": "2024-12-06", "to": "2025-01-10"}]'
    --sources SOURCES  Input sources list, IATA codes (JSON). Example: '["MAD","VLC","BCN"]'
    ```

  - **Extra script to retrieve IATA codes** (thanks to [ip2location-iata-icao project](https://github.com/ip2location/ip2location-iata-icao/)) 😄:

    ```
    python get_iata_codes.py -> returns the complete list of IATA codes per airport.
    ```

## Contribution

Feel free to improve or update the code.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.

