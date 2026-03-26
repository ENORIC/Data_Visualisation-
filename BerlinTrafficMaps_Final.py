import tarfile
import io
import json
import os
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import geopandas as gpd
import streamlit as st
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Berlin Traffic Intelligence", layout="wide")


# Every section of this file is annotated with # comments.
# Each comment block appears at the end of its section and explains:
#   - which specific functions or components are being used
#   - what inputs they take
#   - what that block produces or does
#
# The code is broken into these main sections:
#   1. Imports and page config
#   2. File paths
#   3. Data loading and preprocessing
#   4. Data cleaning and spatial join
#   5. Sidebar navigation
#   6. Dashboard pages — Overview, Time Patterns, Street Analysis,
#      Vehicle Types, Berlin Map, Night Owls, Street DNA, Seasonal Traffic

# ── FILE PATHS ────────────────────────────────────────────────────────────────
XLSX_PATH    = "Stammdaten_Verkehrsdetektion_2022_07_20.xlsx"
BEZIRKE_PATH = "bezirksgrenzen.geojson"
TGZ_FILES    = [
    "detektoren_2024_01.tgz",
    "detektoren_2024_04.tgz",
    "detektoren_2024_07.tgz",
    "detektoren_2024_10.tgz",
]

# ── DATA LOADING and Preprocessing ──────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    # Load detector locations from Excel
    df_locations = pd.read_excel(XLSX_PATH, sheet_name="Stammdaten_TEU_20220720")
    df_locations.columns = df_locations.columns.str.strip()
    df_locations = df_locations.rename(columns={
        'DET_NAME_ALT': 'detector', 'STRASSE': 'street',
        'POSITION': 'location', 'RICHTUNG': 'direction',
        'LÄNGE (WGS84)': 'lon', 'BREITE (WGS84)': 'lat'
    })[['detector', 'street', 'location', 'direction', 'lon', 'lat']]
# pd.read_excel reads the Excel file and loads the correct sheet.
# .str.strip() removes accidental spaces from column names.
# .rename() renames the German column names to English ones.
# The result is a table of all detectors with their street name and GPS coordinates.


    # Load raw traffic data from TGZ files
    def load_tgz(path):
        with tarfile.open(path, 'r:gz') as tar:
            for m in tar.getmembers():
                f = tar.extractfile(m)
                if f:
                    df = pd.read_csv(f, sep=';')
                    df['detector'] = m.name.replace('.csv', '')
                    yield df

    df_raw = pd.concat(
        [df for path in TGZ_FILES for df in load_tgz(path)],
        ignore_index=True
    )
# pd.concat() runs load_tgz() on all 4 TGZ files and stacks every result into one big table.
# ignore_index=True resets the row numbers so they run continuously across all files.


    df = df_raw.rename(columns={
        'Datum (Ortszeit)': 'date',
        'Stunde des Tages (Ortszeit)': 'hour',
        'Vollständigkeit': 'completeness',
        'qkfz': 'vehicles',
        'qpkw': 'cars',
        'qlkw': 'trucks',
        'vkfz': 'speed_avg',
    })[['date', 'hour', 'completeness', 'vehicles', 'cars', 'trucks', 'speed_avg', 'detector']]
# .rename() translates the German column names into English.
#  At the end keeps only the columns that are actually needed, dropping the rest.

    df = df.merge(df_locations, on='detector', how='left')
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.month
    df['dayofweek'] = df['date'].dt.dayofweek
    df['is_weekend'] = df['dayofweek'] >= 5
# .merge() attaches the street name and GPS coordinates to each row using the detector ID as the key.
# pd.to_datetime() converts the date column from plain text into a real date object.
# .dt.month and .dt.dayofweek extract the month number and day of week from that date.
# is_weekend flags True for any row where dayofweek is 5 (Saturday) or 6 (Sunday).


# Data cleaning-------------------------------------------------------------
    df_clean = df.dropna(subset=['vehicles', 'speed_avg'])
# .dropna() removes any rows where vehicle count or speed data is missing.
# As haveing anomalies in the code would bother the analysis 
    # Spatial join — assign each detector to a Berlin district (Bezirk)
    detectors_geo = gpd.GeoDataFrame(
        df_locations,
        geometry=gpd.points_from_xy(df_locations['lon'], df_locations['lat']),
        crs='EPSG:4326'
    )
    bezirke = gpd.read_file(BEZIRKE_PATH).to_crs('EPSG:4326')
    detectors_bezirke = gpd.sjoin(
        detectors_geo,
        bezirke[['Gemeinde_name', 'geometry']],
        how='left',
        predicate='intersects'
    )[['detector', 'Gemeinde_name']].drop_duplicates(subset='detector')

 # gpd.GeoDataFrame() converts the detector table into a geographic object using the lon/lat columns.
# gpd.points_from_xy() turns the longitude and latitude numbers into actual map points.
# crs='EPSG:4326' sets the coordinate system to standard GPS coordinates. It is the universal standard
# gpd.read_file() loads the Berlin district borders from the GeoJSON file.
# .to_crs() makes sure both the detectors and district borders use the same coordinate system.
# gpd.sjoin() checks which district each detector map point falls inside.
# .drop_duplicates() makes sure each detector only gets assigned to one district.

    df_clean = df_clean.merge(detectors_bezirke, on='detector', how='left')

    return df_clean, df_locations
# .merge() adds the district name column to the clean traffic table using detector ID as the key.
# return sends back two tables showing the full clean traffic data and the detector locations.

df_clean, df_locations = load_data()

with open(BEZIRKE_PATH) as f:
    gj_bezirke = json.load(f)

# ── SIDEBAR  ────────────────────────────────────────────────────────
page = st.sidebar.selectbox("Navigate", [
    "Overview", "Time Patterns", "Street Analysis",
    "Vehicle Types", "Berlin Map", "Night Owls", "Street DNA", "Seasonal Traffic Across Berlin"
])
# st.sidebar places the navigation on the left side panel of the dashboard.
# selectbox() creates a dropdown menu with all 8 page names listed.
# The selected page name gets stored in the variable 'page'.


# ── OVERVIEW ──────────────────────────────────────────────────────────────────
if page == "Overview":
    st.title("Berlin Traffic Intelligence 2024")


    st.markdown("""
    Berlin has two distinct rhythms, during the day the commuters use it and it belongs to the freight by night. However, beneath all that each neighborhood, street and diffrent hours in a day reveals a distinct narrative. 
    
    This dasboard was created for those who need to comprehend those narratives, such as; Urban Planning choosing where to make infratructure investments, city officials controlling traffic and companies looking for sites where accessibility and foot traffic truly coincide.
                
    460 Detectors from all around berlin which were collected in January, April, July and October of 2024 spcifically picking the four prominent seasons: Winter, Spring, Summer and Autumn. 
    These observations dont just explain how Berlin movies but also highlight the areas of pressure, underserved areas of the city and opportunities that are just waiting. 
                
    """)

    st.markdown("---")
    st.subheader("What do you want to explore? it is all in here")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Time Patterns**")
        st.caption("When does Berlin move? See how traffic builds through the day and how weekends tell a completely different story to weekdays.")

        st.markdown("**Street Analysis**")
        st.caption("Which streets carry the most traffic? Where does the city slow down and where does speed defy expectation?")

        st.markdown("**Vehicle Types**")
        st.caption("Cars dominate the day, but trucks own the night. Explore how the mix of vehicles shifts hour by hour across the city.")

        st.markdown("**Berlin Map**")
        st.caption("A district-level choropleth showing which Bezirke carry the heaviest average traffic load.")

    with col_b:
        st.markdown("**Night Owls**")
        st.caption("Some streets are busier at 2am than at 8am. Find out which parts of Berlin come alive after dark.")

        st.markdown("**Speed Paradox**")
        st.caption("More traffic should mean slower speeds — but Berlin's motorways break that rule. Volume alone doesn't predict speed.")

        st.markdown("**Seasonal Traffic Across Berlin**")
        st.caption("Which streets come alive in summer? See the seasonal shift between Berlin's coldest and warmest months.")

# ── TIME PATTERNS ─────────────────────────────────────────────────────────────
elif page == "Time Patterns":
    st.title("Time Patterns")

    tab1, tab2 = st.tabs(["Rush Hour", "Weekday vs Weekend"])

    with tab1:
        # Insight 1 — Traffic Distribution by Hour
        sample = df_clean[['hour', 'vehicles']].sample(50000, random_state=42)
        fig = px.box(
            sample,
            x='hour', y='vehicles',
            title='Traffic Distribution by Hour of Day',
            labels={'hour': 'Hour of Day', 'vehicles': 'Vehicles per Hour'},
            color_discrete_sequence=['IndianRed']
        )
        fig.update_layout(plot_bgcolor='white', yaxis_range=[0, 800])
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("""
        The city is quite peaceful and steady during hours 0-4, with most detectors showing fewer than 100 cars. Eventually hour five arrives, everything is diffrent. The spread only gets worse by hour six, when the boxes are already wide indicating that some streets are already crowded while others are persumably still asleep. 
        
        Peak is actually between hour 14 and 16, well not the 9 A.M. rush that one would expect. It is also noteworthy that there is a significant variation between streets beacuse the boxes are tal even during peak hours. At the same hour, one detector may read 500 vehicles, while another may read 50. Berlin doesn't move as one.
        """)   
# .sample(50000) :--> picks 50,000 random rows to keep the chart fast, pllotting all rows would be too slow and time consuming
# random_state=42 makes sure the same 50,000 rows are picked every time the app loads.
# px.box() creates a box plot showing the spread of vehicle counts for each hour of the day.
# color_discrete_sequence sets the box colour to IndianRed.
# fig.update_layout() sets the background to white and caps the y-axis at 800 vehicles.

    with tab2:
        # Insight 2 — Weekday vs Weekend
        weekday = df_clean[df_clean['is_weekend'] == False].groupby('hour')['vehicles'].mean().round(1)
        weekend = df_clean[df_clean['is_weekend'] == True].groupby('hour')['vehicles'].mean().round(1)

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=weekday.index, y=weekday.values, name='Weekday', fill='tozeroy', line=dict(color='tomato')))
        fig2.add_trace(go.Scatter(x=weekend.index, y=weekend.values, name='Weekend', fill='tozeroy', line=dict(color='cornflowerblue')))
        fig2.update_layout(
            title='Weekday vs Weekend Traffic',
            xaxis_title='Hour of Day', yaxis_title='Avg Vehicles',
            plot_bgcolor='white', height=450
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown("""
        The two lines convey quite diffrent narratives. Weekdays see a sharp increase starting at hour five which is expected as the thats when the commute begins perhaps a morning rush and continuing through the afternoon before declining after eighteen. That's not what weekends do at all. 
        
        The graph begin show a higher peak at midnight and then remain sient and flat through the early morning which then gradually increase until they reach their peak at hours 14 and 15. There is huge distance between them in the mornning. 
        
        However, observe what transpires after the hour 20, where weekdays decline while the weekend line remains stable. In fact, weekdays completely give way to the weekend after midnight. The city doesn't stop, it just shifts to whoever using these roads.
        """)          
# is_weekend == False / True filters the data into two separate groups whihc are weekdays and weekends.
# .groupby('hour').mean() calculates the average vehicle count for each hour in each group.
# go.Figure() creates a blank chart that traces can be added to manually.
# go.Scatter() adds a line for each group showing in tomato red for weekdays, cornflower blue for weekends.
# fill='tozeroy' fills the area under each line down to zero, making the difference more visible.
# fig2.update_layout() adds titles, axis labels and sets the chart height to 450px.


# ── STREET ANALYSIS ───────────────────────────────────────────────────────────
elif page == "Street Analysis":
    st.title("Street Analysis")

    tab1, tab2, tab3 = st.tabs(["Busiest Streets", "Speed Heatmap", "Volatility"])

    with tab1:
        streets = (df_clean.groupby('street')['vehicles']
            .mean().round(1).reset_index()
            .sort_values('vehicles', ascending=False).head(20))

        fig = px.treemap(
            streets, path=['street'], values='vehicles',
            title='Top 20 Busiest Streets showing the Avg Vehicles/Hour',
            color='vehicles', color_continuous_scale='Burgyl',
        )
        fig.update_traces(hovertemplate='%{label}: %{value:.0f} vehicles/hr')
        fig.update_layout(height=400)

        selected = st.plotly_chart(fig, use_container_width=True, on_select='rerun', key='treemap')

    
        if selected and selected.get('selection') and selected['selection'].get('points'):
            street_name = selected['selection']['points'][0].get('label')
            if street_name and street_name in df_clean['street'].values:
                hourly = df_clean[df_clean['street'] == street_name].groupby('hour')['vehicles'].mean().round(1).reset_index()
                fig_hourly = px.line(
                    hourly, x='hour', y='vehicles',
                    title=f'{street_name} — Traffic depending on the Hour of Day',
                    labels={'hour': 'Hour', 'vehicles': 'Avg Vehicles'},
                    markers=True, color_discrete_sequence=['darkorange']
                )
                fig_hourly.update_layout(plot_bgcolor='white', height=350)
                st.plotly_chart(fig_hourly, use_container_width=True)
        else:
            st.caption("Click any of the street blocks above to explore the street's hourly pattern.")
# .groupby('street').mean() calculates the average vehicles per hour for every street.
# .head(20) keeping only the top 20 busiest streets which seemed pretty logical to go as these were the most intresting streets in the dataset.
# px.treemap() draws each street as a rectangle tile where bigger and darker means more traffic.
# color_continuous_scale='Burgyl' sets the colour gradient from a vintage light to dark burgundy.
# hovertemplate customises the tooltip to show the vehicle count when hovering over a block.
# on_select='rerun' makes the app re-run when a block is clicked, capturing which street was selected. very important for the interactive feature of the code 
# The if block checks if a street was clicked and if so filters the data for just that street.
# px.line() then draws an hourly traffic pattern for that specific clicked street below the treemap.


    with tab2:
        # Insight 4 — Speed Heatmap
        top_streets = (df_clean.groupby('street')['vehicles']
                       .mean().sort_values(ascending=False).head(15).index.tolist())
        filtered = df_clean[df_clean['street'].isin(top_streets)]
        pivot = filtered.groupby(['street', 'hour'])['speed_avg'].mean().round(1).unstack()
        fig_heatmap = px.imshow(
            pivot,
            title='Average Speed by Street and Hour',
            labels={'x': 'Hour of Day', 'y': 'Street', 'color': 'Avg Speed (km/h)'},
            color_continuous_scale='Spectral', aspect='auto'
        )
        fig_heatmap.update_layout(height=550)
        st.plotly_chart(fig_heatmap, use_container_width=True)
        st.markdown("""
        * Instead of having a 'Rush Hour' Brunnenstraße more of have a 19 hour red hot fever. It consistently stays in the red zone from 5:00 AM to midnight, indicaitng that the street has permanently exceeded its physical capacity" 
        
        * The Midday sinkhole, in contrast to typical commuter routes,Oberbaumstraße and Schöneberger Ufer collapse in the middle of the day. This 'afternoon slump' is more severe than the morning rush and is probably cause by delivery saturation and midday logistics
        
        * The only exception to high flow is the A115. It's constant green draws attention to the hollow center of the city, where mobility is essentially cut in half regardless of the hour as soon as you would leave the highway and enter the urban grid. 
        """)
# .head(15) selects only the top 15 busiest streets to keep the heatmap readable. Which are the reaasobale ones to take showing the most variance. 
# .isin() filters the main dataframe to only those 15 streets.
# .groupby(['street', 'hour']).mean() calculates the average speed for every street-hour combination which is showed in the graph for the ease of understanding .
# .unstack() pivots the hour column into separate columns, turning it into a grid format.
# px.imshow() draws that grid as a heatmap, each cell is one street at one hour, coloured by speed.
# color_continuous_scale='Spectral' uses red for slow speeds and green/blue for fast speeds.


    with tab3:
        # Insight 8 — Street Volatility
        volatility = df_clean.groupby(['street', 'Gemeinde_name'])['vehicles'].agg(
            mean_traffic='mean',
            std_traffic='std'
        ).round(1).reset_index()
        volatility['cv'] = (volatility['std_traffic'] / volatility['mean_traffic'] * 100).round(1)
        volatility = volatility.dropna()

        med_traffic = volatility['mean_traffic'].median()
        med_cv      = volatility['cv'].median()

        fig3 = px.scatter(
            volatility,
            x='mean_traffic', y='cv',
            hover_name='street',
            color='Gemeinde_name',
            title='Busy Streets Are More Predictable. Except Brunnenstraße.',
            labels={'mean_traffic': 'Avg Vehicles per Hour', 'cv': 'Volatility (%)', 'Gemeinde_name': 'District'},
            size='mean_traffic', size_max=40
        )
        fig3.add_hline(y=med_cv,      line_dash='dash', line_color='gray', opacity=0.5)
        fig3.add_vline(x=med_traffic, line_dash='dash', line_color='gray', opacity=0.5)

        x_max = volatility['mean_traffic'].max()
        y_max = volatility['cv'].max()

        annotations = [
            (med_traffic/2, y_max*0.95, "Quiet & Unpredictable", 'rosybrown'),
            ((med_traffic+x_max)/2, y_max*0.95, "Busy & Unpredictable", 'sienna'),
            (med_traffic/2, med_cv*0.3, "Quiet & Stable", 'darkkhaki'),
            ((med_traffic+x_max)/2, med_cv*0.3, "Busy & Predictable", 'cadetblue'),
        ]

        fig3.update_layout(
            plot_bgcolor='white', height=580,
            annotations=[
                dict(x=x, y=y, text=f"<b>{t}</b>", showarrow=False, font=dict(size=10, color=c), xanchor='center')
                for x, y, t, c in annotations
            ]
        )
        st.plotly_chart(fig3, use_container_width=True)
        st.markdown("""
        * There is a general rule about traffic in Berlin the busier the steet the more regualr the rhythm. The violent exception is Brunnenstraße, at 856 vehicles per hour being the city's heaviest hitter. But it's volatility is an astounding 108%, the unpredictable spikes in nighlife and weekend markets that keep in a state of perpetual change are what isn't set by the 9 to 5 commuters. 
        
        * The more quiet wildcards are located in the upper-left, although there isnt much traffic on these streets it is still impossible to plan for them, for example a single double parked delivery van can cause a significant percentage swing due to thier flow being extremly thin, instantly transforming a 'quite' street into bottleneck. 
        
        * However, the majority of districts tend to be reliable workhouses, there are the city's steady artieries, busy thoroughfares that have discoverd a steady, rhythemic heartbeat that motorists can genuienly rely on.
        """)

# .agg() calculates both the mean and standard deviation of vehicles per street in one step.
# cv (coefficient of variation) is Standard deviaision divided by mean used to measures how unpredictable a street is as a percentage.
# .dropna() removes any streets where the calculation couldn't be completed or cant be possible as some them have null or 0.
# .median() finds the middle value for both traffic and volatility, used to draw the dividing lines.
# px.scatter() plots every street as a dot in the x axis showing how busy it is, y axis is how unpredictable.
# size='mean_traffic' makes busier streets appear as larger dots.
# color='Gemeinde_name' colours each dot by which Berlin district the street belongs to.
# add_hline() and add_vline() draw dashed lines at the median values, splitting the chart into 4 quadrants.
# The annotations list places labels in each quadrant describing what that zone means.


# ── VEHICLE TYPES ─────────────────────────────────────────────────────────────
elif page == "Vehicle Types":
    st.title("Vehicle Types")

    tab1, tab2 = st.tabs(["Volume vs Truck Share", "Truck Rush Hour"])

    with tab1:
        # Insight 5 — Traffic Volume vs Truck Share
        street_stats = df_clean.groupby('street').agg(
            vehicles=('vehicles', 'mean'),
            trucks=('trucks', 'mean'),
            cars=('cars', 'mean')
        ).round(1).reset_index()
        street_stats['truck_pct'] = (street_stats['trucks'] / street_stats['vehicles'] * 100).round(1)

        fig = px.scatter(
            street_stats,
            x='vehicles', y='truck_pct',
            hover_name='street',
            size='vehicles',
            size_max=25,
            title='Traffic Volume vs Truck Share by Street',
            labels={'vehicles': 'Avg Vehicles per Hour', 'truck_pct': 'Truck Share %'},
            color='truck_pct', color_continuous_scale='YlOrRd',
        )
        fig.update_layout(plot_bgcolor='white', height=550)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("""
        * Even though passengers cars make up the majority of the city's surface this graph shows where the real heavy lifting takes place. Berlin's industrial ghosts are represented by the top-left outliers, which are streets with a huge 60 to 70% truck share but little overall traffic. Quite literally specialized logical veins that supply the city while the rest of Berlin is in its slumber.

        * Conversely, the bottom right horizon depicts only commuter territories. Although the number of vehicles is at its highest point which is close to 1,000 per hour but still the truck share is negligible. The 'industrial' and 'residential' heartbeats of the city are clearly separated from one another.

        * The scattered middle zone, even though messy, really answers everything. Heavy car traffic and a moderate truck presence are at odds on these streets. These might be the points of contention where daily commutes and delivery requirements collide, resulting in the unpredictability seen in the other charts.
        """)
# .agg() calculates the average vehicles, trucks and cars per hour for every street in one step.
# truck_pct divides average trucks by total vehicles and multiplies by 100 to get a percentage which can be legible when you hover thorugh the graph.
# px.scatter() plots every street as a dot where x axis is total traffic, y axis is truck share percentage.
# size='vehicles' makes the dots bigger for streets with more total traffic.
# color='truck_pct' with color_continuous_scale='YlOrRd' colours dots from yellow show the low truck share to red (high truck share).
# hover_name='street' shows the street name when hovering over a dot.
    with tab2:
        # Insight 6 — Trucks Have Their Own Rush Hour
        hourly = df_clean.groupby('hour').agg(
            cars=('cars', 'mean'),
            trucks=('trucks', 'mean')
        ).round(1).reset_index()
        hourly['truck_share'] = (hourly['trucks'] / (hourly['cars'] + hourly['trucks']) * 100).round(1)

        fig2 = go.Figure()
        fig2.add_trace(go.Scatterpolar(
            r=hourly['truck_share'],
            theta=hourly['hour'] * 15,
            fill='toself',
            line=dict(color='palevioletred')
        ))
        fig2.update_layout(
            title='Trucks Have Their Own Rush Hour — Berlin 2024',
            polar=dict(
                angularaxis=dict(
                    tickmode='array',
                    tickvals=list(range(0, 360, 15)),
                    ticktext=[f"{h}:00" for h in range(24)],
                    direction='clockwise',
                    rotation=90
                ),
                radialaxis=dict(ticksuffix='%')
            ),
            height=500
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown("""
        * The Ghost Shift, considered to be the most crucial period when trucks runs the streets while the passenger cars disappear, which is marked by the enourmous 4:00 AM spike. The city's supply chain can only operate at maximum capacity during this period without causing commuter conflict. 
        
        * The story truns around 3:00 P.M. as the afternoon commuter surge takes over, truck share hits its daily floor and is compelled to make a retreat. The city clearly shows two distinct cycles -> Residential during the day and Industrial during the night.
        """)
# .agg() calculates the average cars and trucks across all streets for each hour of the day.
# truck_share divides trucks by total vehicles that is the sum of cars + trucks to get the truck percentage per hour.
# go.Figure() creates a blank polar chart that a trace can be added to manually.
# go.Scatterpolar() draws the truck share as a shape on a circular clock-face chart. "which looks like a spider web showing the spread but over here its the truck spread"
# r= sets the distance from the centre the truck share value and "theta= sets the angle the hour, which is neccassy as this shows the shape.""
# hourly['hour'] * 15 converts each hour into degrees so 24 hours fills the full 360 degree circle.
# fill='toself' fills the inside of the shape to make the pattern more visible.
# angularaxis ticktext labels each position on the circle with the matching hour e.g. 0:00, 1:00.
# direction='clockwise' for the ease of reading and rotation=90 make the chart read like a normal clock starting from the top.

# ── BERLIN MAP ───────────────────────────────────────────────────────────────
elif page == "Berlin Map":
    st.title("Berlin Traffic by District")

    # compute all three metrics
    rush = df_clean[df_clean['hour'].isin([7,8,9])].groupby('Gemeinde_name')['vehicles'].mean()
    offpeak = df_clean[df_clean['hour'].isin([1,2,3,4])].groupby('Gemeinde_name')['vehicles'].mean()
    overall = df_clean.groupby('Gemeinde_name')['vehicles'].mean()

    pressure = pd.DataFrame({
        'Rush Hour from 7:00 a.m to 9:00 a.m': rush,
        'Off-Peak from 1:00 a.m. to 4:00 a.m.': offpeak,
        'Congestion Pressure (%)': ((rush - offpeak) / offpeak * 100).round(1)
    }).dropna().reset_index()

# .isin([7,8,9]) filters rows to only morning rush hours, .isin([1,2,3,4]) for the dead of night.
# .groupby('Gemeinde_name').mean() calculates the average vehicles per hour for each district.
# pd.DataFrame() combines all three metrics into one table with each district as a row.
# Congestion Pressure divides the difference between rush and offpeak by offpeak to show how much busier each district gets during rush hour as a percentage.
# .dropna() removes any districts where the calculation couldn't be completed.

    # dropdown for the selection 
    metric = st.selectbox("Select view", ['Rush Hour from 7:00 a.m to 9:00 a.m', 'Off-Peak from 1:00 a.m. to 4:00 a.m.', 'Congestion Pressure (%)'])

    fig = px.choropleth_mapbox(
        pressure,
        geojson=gj_bezirke,
        locations='Gemeinde_name',
        featureidkey='properties.Gemeinde_name',
        color=metric,
        color_continuous_scale='Plasma',
        mapbox_style='carto-positron',
        zoom=10,
        center={'lat': 52.52, 'lon': 13.405},
        opacity=0.8,
        title=f'{metric} by District — Berlin 2024',
        labels={metric: metric, 'Gemeinde_name': 'District'}
    )
    fig.update_layout(height=600, margin=dict(l=0, r=0, t=40, b=0))
    fig.update_traces(marker_line_width=0.5, marker_line_color='white')
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("""
    **Rush Hour** :—> average vehicles per hour between 7:00 a.m to 9:00 a.m per district.
    
    **Off-Peak** :—> average vehicles per hour between 1:00 a.m. to 4:00 a.m. district.
    
    **Congestion Pressure** :—> how much busier rush hour is compared to off-peak, as a percentage. 
    The higher the number, the more the district transforms during morning rush.
    """)
# px.choropleth_mapbox() draws Berlin's districts as coloured shapes on a real polygon map uploaded before.
# geojson=gj_bezirke provides the actual border coordinates for each district.
# featureidkey='properties.Gemeinde_name' tells Plotly which field in the GeoJSON matches the district name column.
# color=metric colours each district based on whichever metric the user selected in the dropdown.
# color_continuous_scale='Plasma' sets the colour gradient from dark purple being low to bright yellow being high.
# mapbox_style='carto-positron' sets the background map to a clean light grey style.
# center and zoom set the map's starting position and zoom level over Berlin.
# marker_line_width and marker_line_color draw thin white borders between districts.

# ── NIGHT OWLS ────────────────────────────────────────────────────────────────
elif page == "Night Owls":
    st.title("Night Owl Streets")

    night = df_clean[df_clean['hour'].isin([0,1,2,3,4])].groupby('street')['vehicles'].mean()
    day = df_clean[df_clean['hour'].isin([7,8,9])].groupby('street')['vehicles'].mean()

    owls = pd.DataFrame({'night': night, 'day': day}).dropna()
    owls['ratio'] = (owls['night'] / owls['day']).round(3)
    owls = owls.sort_values('ratio', ascending=False).reset_index()
    owls['rank'] = range(len(owls))
    top10 = owls.nlargest(10, 'ratio').index
    owls['label'] = ''
    owls.loc[top10, 'label'] = owls.loc[top10, 'street']

# .isin([0,1,2,3,4]) filters to night hours and .isin([7,8,9]) filters to the morning rush hours.
# .groupby('street').mean() calculates the average vehicles per hour for each street in each time window that is in the 24 hour cycle.
# pd.DataFrame() combines both into one table with night and day as separate columns.
# ratio divides night traffic by day traffic, a ratio above 1.0 means the street is busier at night as in thats is the threshold kept to see if there are any streets that lie above that line.
# .sort_values() orders streets from highest to lowest ratio.
# .nlargest(10, 'ratio') finds the top 10 streets with the highest night to day ratio.
# owls['label'] starts as empty for all streets, then only fills in the street name for those top 10.
# This means only the top 10 streets get a visible label on the chart, keeping it clean.

    fig = px.scatter(
        owls,
        x='night', y='ratio',
        hover_name='street',
        text='label',
        size='night',
        size_max=20,
        color='ratio',
        color_continuous_scale='RdBu_r',
        title='Night to Day Traffic Ratio of every street in Berlin',
      labels={'night': 'Night Traffic', 'ratio': 'Night to Day Ratio'}
    )
    fig.add_hline(y=1.0, line_dash='dash', line_color='black', annotation_text='Equal (ratio = 1.0)')
    fig.update_traces(textposition='top center', textfont_size=10)
    fig.update_layout(plot_bgcolor='white', height=550)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("""
    Over here, each dot represent a street. The higher the dot the more traffic it carries at night relative to the morning hustle and bustle. 
    
    The dashed line along the grah is a threshold of 1.0 and if a street croses it, that street is considered to be genuinely busier in midnight than in the common rush hour.
                
    Berlin does sleep or does it? 
    Each size of the dot inidicates the actual amount of nighttime traffic on that street. 
    * A small dot high up indicates a queit street that still manages to remain resounable busy at night.
    * A large dot high up would show the street that is busy at night and defies the datime rush. 
    """)

# px.scatter() plots every street as a dot that is where x axis shows how much night traffic is there, y axis shows the ratio.
# size='night' the dots becomes bigger for streets that have more actual nighttime volume.
# color='ratio' with color_continuous_scale='RdBu_r' colours high ratio streets red and low ratio streets blue.
# text='label' displays the street name directly on the chart but only for the top 10 streets.
# textposition='top center' places those labels just above their dot hence making it easier to read .
# add_hline() draws a dashed black line at ratio 1.0 as the threshold between day and night dominant streets.
# annotation_text labels that line so the viewer knows what it represents.


# ── STREETT SPEED PARADOX ─────────────────────────────────────────────────────────────
elif page == "Street DNA":
    st.title("Street DNA")

    # weekend boost per street
    weekday_avg = df_clean[df_clean['is_weekend'] == False].groupby('street')['vehicles'].mean()
    weekend_avg = df_clean[df_clean['is_weekend'] == True].groupby('street')['vehicles'].mean()
    weekend_boost = ((weekend_avg - weekday_avg) / weekday_avg * 100).round(1)

    metrics = df_clean.groupby('street').agg(
        cars=('cars', 'mean'),
        speed=('speed_avg', 'mean'),
        trucks=('trucks', 'mean'),
        volatility=('vehicles', 'std')
    ).round(1)

    metrics['freight_share'] = (metrics['trucks'] / (metrics['cars'] + metrics['trucks']) * 100).round(1)
    metrics['weekend_boost'] = weekend_boost

    for col in ['cars', 'speed', 'freight_share', 'volatility', 'weekend_boost']:
        metrics[col] = ((metrics[col] - metrics[col].min()) /
                        (metrics[col].max() - metrics[col].min())).round(3)

    metrics = metrics.dropna()

# is_weekend == False or True by spliting the data into weekdays and weekends to calculate average vehicles for each.
# weekend_boost measures how much busier each street is on weekends compared to weekdays as a percentage.
# .agg() calculates average cars, average speed, average trucks and Standard deviasion of vehicles for every street in one step.
# std (standard deviation) is used as the volatility measure where higher the standard means more unpredictable traffic.
# freight_share divides trucks by total vehicles to get the percentage of freight traffic per street.
# The for loop applies min-max normalisation to every metric, rescaling all values to sit between 0 and 1.
# This is needed so that cars, speed, freight and volatility can all be fairly compared on the same chart scale.
# .dropna() removes streets where any metric couldn't be calculated.


    top_cars = metrics['cars'].nlargest(2).index.tolist()
    top_freight = metrics['freight_share'].nlargest(2).index.tolist()
    top_volatile = metrics['volatility'].nlargest(2).index.tolist()
    default = sorted(set(top_cars + top_freight + top_volatile))

    streets_to_show = st.multiselect(
        "Compare streets: Select up to 6",
        options=sorted(metrics.index.tolist()),
        default=default,
        max_selections=6
    )
# .nlargest(2) picks the top 2 streets for cars, freight and volatility to use as default selections.
# set() removes any duplicates in case the same street appears in multiple top 2 lists.
# st.multiselect() creates a searchable dropdown scroll bar where the user can pick up to 6 streets to compare.
# default=default pre-selects the most interesting streets when the page first loads.
# max_selections=6 caps the selection so the radar chart doesn't get too cluttered.

    categories = ['Cars/hr', 'Speed', 'Freight Share', 'Volatility', 'Weekend Boost']

    fig = go.Figure()
    for street in streets_to_show:
        if street in metrics.index:
            row = metrics.loc[street]
            fig.add_trace(go.Scatterpolar(
                r=[row['cars'], row['speed'], row['freight_share'], row['volatility'], row['weekend_boost'], row['cars']],
                theta=categories + [categories[0]],
                fill='toself',
                name=street,
                opacity=0.6
            ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
        title='Street DNA, A Multi-dimensional Profile :)',
        height=600
    )
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("""
    Every street in berlin has a fingerprint, a DNA in others words, as you can see. 
    
    Upto 6 dimensions can be simutaneously covered by each coloured shape showing the number of passing cars, the speed and also the percentage of freight traffic,along with the hourly volatility of the flow, and whether the street  is livelier on weekends that on weekdays. 
                
    A broad shape indicates dominance in several dimensions. A narrow spike indicates that the street is average everywhere else but extreme in one place.
    """)
# go.Figure() creates a blank chart that each street's shape gets added to one by one.
# The for loop iterates through every selected street and adds one radar shape per street.
# go.Scatterpolar() draws each street as a polygon on a circular radar chart.
# r= sets the value for each axis using the 5 normalised metrics for that street.
# r repeats the first value at the end to close the shape back to its starting point.
# theta= sets the 5 axis labels around the chart, also repeated to close the loop.
# fill='toself' fills the inside of each shape with colour so streets are easy to compare visually and to look dope fr. :)
# opacity=0.6 makes shapes slightly transparent so overlapping streets remain visible.
# radialaxis range=[0,1] keeps all axes on the same 0 to 1 scale set during normalisation.

# ── Months ───────────────────────────────────────────────────────────
elif page == "Seasonal Traffic Across Berlin":

    months = [1, 4, 7, 10]
    month_names = {1: 'January', 4: 'April', 7: 'July', 10: 'October'}

    df_months = df_clean[df_clean['month'].isin(months)]
    district_monthly = (df_months.groupby(['Gemeinde_name', 'month'])['vehicles']
                        .mean().round(1).reset_index())

    vmin = district_monthly['vehicles'].min()
    vmax = district_monthly['vehicles'].max()

    # track which map is expanded
    if 'expanded_month' not in st.session_state:
        st.session_state.expanded_month = None

# months list defines the 4 seasons being compared and month_names maps each number to its name as we only take Jan, Apr, Jul and Oct.
# .isin(months) filters the data to only rows from those 4 months.
# .groupby(['Gemeinde_name', 'month']).mean() calculates average vehicles per district per month.
# vmin and vmax is used to store the lowest and highest vehicle values across all months and districts.
# These are used later to lock the colour scale so all 4 maps are directly comparable.
# st.session_state stores which month is currently expanded whihc it persists across page reruns.
# If no month has been clicked yet, expanded_month is set to None by default.

    def make_map(month, zoom, height, show_colorbar):
        month_data = district_monthly[district_monthly['month'] == month].copy()
        fig = px.choropleth_mapbox(
            month_data,
            geojson=gj_bezirke,
            locations='Gemeinde_name',
            featureidkey='properties.Gemeinde_name',
            color='vehicles',
            color_continuous_scale=[
                [0.0, 'mintcream'],
                [0.3, 'darkseagreen'],
                [0.6, 'forestgreen'],
                [1.0, 'darkgreen']
            ],
            range_color=[vmin, vmax],
            mapbox_style='carto-positron',
            zoom=zoom,
            center={'lat': 52.52, 'lon': 13.405},
            opacity=0.75,
            hover_data={'vehicles': ':.0f', 'Gemeinde_name': True},
            labels={'vehicles': 'Avg vehicles/hr', 'Gemeinde_name': 'District'}
        )
        fig.update_layout(
            height=height,
            margin=dict(l=0, r=0, t=0, b=0),
            coloraxis_showscale=show_colorbar,
            coloraxis_colorbar=dict(title='Avg vehicles/hr') if show_colorbar else {}
        )
        return fig
    
# make_map() is a reusable function that builds one choropleth map for a given month.
# It takes zoom, height and show_colorbar as arguments so the same function works for both
# the small grid view and the large expanded view without writing the map code twice.
# range_color=[vmin, vmax] locks the colour scale to the same range across all 4 maps.
# The custom color_continuous_scale goes from mintcream which indicates low traffic to darkgreen which indiactes high traffic).
# show_colorbar controls whether the colour legend is shown only on one map in the grid shows it to avoid repetition.
# The function returns the finished figure so it can be rendered wherever it's called.

    # --- expanded view ---
    if st.session_state.expanded_month is not None:
        m = st.session_state.expanded_month
        st.title(f"Seasonal Traffic — {month_names[m]}")

        if st.button('← Back to all months'):
            st.session_state.expanded_month = None
            st.rerun()

        fig = make_map(m, zoom=10, height=680, show_colorbar=True)
        st.plotly_chart(fig, use_container_width=True)

        # district table below the expanded map
        month_data = district_monthly[district_monthly['month'] == m].copy()
        month_data = month_data.sort_values('vehicles', ascending=False).reset_index(drop=True)
        month_data.index += 1
        month_data.columns = ['District', 'Month', 'Avg vehicles/hr']
        st.dataframe(month_data[['District', 'Avg vehicles/hr']], use_container_width=True)

# If a month has been clicked, the app switches to expanded view for that month.
# st.button('← Back') resets expanded_month to None and st.rerun() refreshes the page back to grid view.
# make_map() is called with a larger zoom and height to fill the screen in expanded mode.
# .sort_values('vehicles', ascending=False) ranks districts from busiest to quietest.
# month_data.index += 1 starts the table numbering from 1 instead of 0.
# st.dataframe() renders the ranked district table below the expanded map.

    # --- grid view ---
    else:
        st.title('Seasonal Traffic Across Berlin')
        st.caption('Click on a month to expand the map and see district details')

        col1, col2 = st.columns(2)
        columns = [col1, col2, col1, col2]

        for i, month in enumerate(months):
            with columns[i]:
                st.subheader(month_names[month])
                fig = make_map(month, zoom=8.5, height=370, show_colorbar=(i == 1))
                st.plotly_chart(fig, use_container_width=True)
                if st.button(f'Expand {month_names[month]}', key=f'btn_{month}'):
                    st.session_state.expanded_month = month
                    st.rerun()
# st.columns(2) creates a two column layout for the grid view.
# columns list maps each of the 4 months alternately into col1 and col2 to fill a 2x2 grid.
# The for loop renders all 4 maps by calling make_map() once per month at a smaller size.
# show_colorbar=(i == 1) only shows the colour legend on the second map (April) to keep the grid clean.
# st.button() adds an expand button under each map with a unique key so Streamlit can tell them apart.
# Clicking a button sets expanded_month to that month and st.rerun() switches the page to expanded view.