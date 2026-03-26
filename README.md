 
This is the Final project for Data Driven Visualisation 

## Berlin Traffic Intelligence Dashboard
- Exploring Traffic Patterns, Street Behaviour & Seasonal Shifts Across Berlin
- By — Enosh Paul Niju GH1026595

My initial motivation for this project was curiosity about how a city actually moves. 
The simple question being "Could Berlin's traffic data tell us something deeper than just 
rush hour?"

This project is entirely focused on data analysis and interactive visualisation. 
460 detectors placed across Berlin, recording every hour of every day across four seasons 
in 2024, made it the perfect dataset to explore urban mobility patterns.

## Data Source
*Dataset:* Berlin Open Data 
*Source:* https://daten.berlin.de/datensaetze/verkehrsdetektion-berlin

*Dataset:* •	Open Data Information Berlin (ODIS)
*Source:* https://daten.odis-berlin.de/en/dataset/bezirksgrenzen/

*Stream lit Dashboard link: -->*
https://berlintrafficintelligenceeno.streamlit.app/ 

- Master detector info: Stammdaten_Verkehrsdetektion_2022_07_20.xlsx
- District boundaries: bezirksgrenzen.geojson
- Traffic recordings: 4 seasonal TGZ files (January, April, July, October)

For the detectors reading around berlin was specifically targeted for the year 2024 for this analysis was based on data integrity and analytical completeness a simple strategic decision in other words. Even through data from 2025 might be accessible, it frequently lacks the “New Quality Assurance” cleaning done by the portal officials. The 2024 data reading are much more “settled” meaning that outliers and detector issues have already been identified or fixed by local authorities.  

The “Geo-spatial map” in this case was the “Beziksgrenzen” GeoJSON file from “ODIS” which is specifically chosen because of the map’s “district boundaries” which is very much utilized to its best potential. 


## Code Documentation

The Python file `BerlinTrafficMaps_Final.py` is annotated throughout with `#` comments.
Each comment block appears at the end of its section and explains which specific functions 
and components are being used and what that block of code produces.


## Table of Contents
- Overview
- Time Patterns — Rush Hour & Weekday vs Weekend
- Street Analysis — Busiest Streets, Speed Heatmap & Volatility
- Vehicle Types — Volume vs Truck Share & Truck Rush Hour
- Berlin Map — District level choropleth
- Night Owls — Streets that come alive after dark
- Street DNA — Multi-dimensional street profiles
- Seasonal Traffic Across Berlin

## Tools Used

- **Python / Streamlit — dashboard framework**
- **Pandas — data loading and preprocessing**
- **GeoPandas — spatial joins and district mapping**
- **Plotly — interactive visualisations**
- **Tarfile — reading compressed seasonal data files**
