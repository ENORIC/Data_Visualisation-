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

# ── FILE PATHS ────────────────────────────────────────────────────────────────
XLSX_PATH    = "Stammdaten_Verkehrsdetektion_2022_07_20.xlsx"
BEZIRKE_PATH = "bezirksgrenzen.geojson"
TGZ_FILES    = [
    "data/detektoren_2024_01.tgz",
    "data/detektoren_2024_04.tgz",
    "data/detektoren_2024_07.tgz",
    "data/detektoren_2024_10.tgz",
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



    df = df_raw.rename(columns={
        'Datum (Ortszeit)': 'date',
        'Stunde des Tages (Ortszeit)': 'hour',
        'Vollständigkeit': 'completeness',
        'qkfz': 'vehicles',
        'qpkw': 'cars',
        'qlkw': 'trucks',
        'vkfz': 'speed_avg',
    })[['date', 'hour', 'completeness', 'vehicles', 'cars', 'trucks', 'speed_avg', 'detector']]

    df = df.merge(df_locations, on='detector', how='left')
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.month
    df['dayofweek'] = df['date'].dt.dayofweek
    df['is_weekend'] = df['dayofweek'] >= 5



# Data cleaning-------------------------------------------------------------
    df_clean = df.dropna(subset=['vehicles', 'speed_avg'])

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

    df_clean = df_clean.merge(detectors_bezirke, on='detector', how='left')

    return df_clean, df_locations

df_clean, df_locations = load_data()

with open(BEZIRKE_PATH) as f:
    gj_bezirke = json.load(f)

# ── SIDEBAR  ────────────────────────────────────────────────────────
page = st.sidebar.selectbox("Navigate", [
    "Overview", "Time Patterns", "Street Analysis",
    "Vehicle Types", "Berlin Map", "Night Owls", "Street DNA", "Seasonal Traffic Across Berlin"
])

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

    # dropdown
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