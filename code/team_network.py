import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network
import tempfile
import os
from bs4 import BeautifulSoup
import requests
import pycountry

# --- Streamlit Page Config ---
st.set_page_config(page_title="Football Team Network", page_icon="⚽", layout="wide")
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            #header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# === Custom Flag Handling ===
custom_country_emoji = {
    "England": "🏴",
    "Scotland": "🏴",
    "Wales": "🏴",
    "Northern Ireland": "🏴",
    "Kosovo": "🇽🇰",
    "Ivory Coast": "🇨🇮",
    "Congo": "🇨🇬",
    "DR Congo": "🇨🇩",
    "South Korea": "🇰🇷",
    "North Korea": "🇰🇵"
}

custom_country_flags = {
    "England": "https://upload.wikimedia.org/wikipedia/en/b/be/Flag_of_England.svg",
    "Scotland": "https://upload.wikimedia.org/wikipedia/commons/1/10/Flag_of_Scotland.svg",
    "Wales": "https://upload.wikimedia.org/wikipedia/commons/d/dc/Flag_of_Wales.svg",
    "Northern Ireland": "https://upload.wikimedia.org/wikipedia/commons/d/d0/Ulster_banner.svg",
    "Kosovo": "https://flagcdn.com/32x24/xk.png",
    "Cote d'Ivoire": "https://flagcdn.com/32x24/ci.png",
    "Congo": "https://flagcdn.com/32x24/cg.png",
    "DR Congo": "https://flagcdn.com/32x24/cd.png",
    "Korea": "https://flagcdn.com/32x24/kr.png",
    "North Korea": "https://flagcdn.com/32x24/kp.png",
    "Northern Ireland": "https://tmssl.akamaized.net//images/flagge/verysmall/192.png?lm=1520611569"
    
}


def country_to_emoji(country_name):
    if country_name in custom_country_emoji:
        return custom_country_emoji[country_name]
    try:
        country = pycountry.countries.get(name=country_name)
        if not country:
            for c in pycountry.countries:
                if country_name.lower() in [c.name.lower(), getattr(c, 'official_name', '').lower()]:
                    country = c
                    break
        if country:
            code = country.alpha_2.upper()
            return chr(ord(code[0]) + 127397) + chr(ord(code[1]) + 127397)
    except:
        pass
    return "❓"


def country_to_flag_url(country_name):
    if country_name in custom_country_flags:
        return custom_country_flags[country_name]
    try:
        country = pycountry.countries.get(name=country_name)
        if not country:
            for c in pycountry.countries:
                if country_name.lower() in [c.name.lower(), getattr(c, 'official_name', '').lower()]:
                    country = c
                    break
        if country:
            code = country.alpha_2.lower()
            return f"https://flagcdn.com/32x24/{code}.png"
    except:
        return None


emoji_flag_mapping = {c.name: country_to_emoji(c.name) for c in pycountry.countries}
emoji_flag_mapping.update(custom_country_emoji)

# === League and Team scraping ===
LEAGUE_URLS = {
    "Premier League": "https://www.transfermarkt.com/premier-league/startseite/wettbewerb/GB1",
    "La Liga": "https://www.transfermarkt.com/laliga/startseite/wettbewerb/ES1",
    "Ligue 1": "https://www.transfermarkt.com/ligue-1/startseite/wettbewerb/FR1",
    "Serie A": "https://www.transfermarkt.com/serie-a/startseite/wettbewerb/IT1",
    "Bundesliga": "https://www.transfermarkt.com/bundesliga/startseite/wettbewerb/L1",
    "Malaysia Super League": "https://www.transfermarkt.com/malaysia-super-league/startseite/wettbewerb/MYS1",
}

@st.cache_data(show_spinner=False)
def get_teams_by_league(league_url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(league_url, headers=headers)
    if response.status_code != 200:
        st.error(f"Failed to fetch teams: {response.status_code}")
        return {}
    soup = BeautifulSoup(response.content, 'html.parser')
    teams = {}
    for td in soup.find_all('td', class_="hauptlink no-border-links"):
        a = td.find('a', href=True)
        if a:
            team_name = a.get('title', a.text.strip())
            relative_url = a['href']
            if "/startseite/verein" in relative_url:
                full_url = "https://www.transfermarkt.com" + relative_url
                teams[team_name] = full_url
    return teams

@st.cache_data(show_spinner=False)
def scrape_team(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        st.error(f"Failed to load page: {response.status_code}")
        return pd.DataFrame()

    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table', {'class': 'items'})
    rows = table.find('tbody').find_all('tr', recursive=False)

    players = []
    for row in rows:
        cols = row.find_all('td', recursive=False)
        if len(cols) < 5:
            continue

        jersey_number = cols[0].get_text(strip=True)
        name_cell = cols[1].find('td', class_='hauptlink')
        name = name_cell.find('a').get_text(strip=True) if name_cell and name_cell.find('a') else ''
        position_cell = cols[1].find_all('td')[-1]
        position = position_cell.get_text(strip=True) if position_cell else ''
        dob_age_text = cols[2].get_text(strip=True)
        dob, age = (dob_age_text.split('(')[0].strip(), dob_age_text.split('(')[-1].replace(')', '').strip()) if '(' in dob_age_text else (dob_age_text.strip(), '')
        nat_imgs = cols[3].find_all('img')
        nationality = ', '.join(img.get('title', '') for img in nat_imgs)
        market_value = cols[4].get_text(strip=True)

        players.append({
            "Jersey Number": jersey_number,
            "Name": name,
            "Position": position,
            "Date of Birth": dob,
            "Age": age,
            "Nationality": nationality,
            "Market Value": market_value
        })

    return pd.DataFrame(players)

# === UI ===
st.title("🕸️ Football Squad Player Network")
st.subheader("Network Graph by Position, Nationality, Market Value & Age")

# === User-Defined Team URL ===
st.sidebar.markdown("### 🔗 Other Team URL")

# Sidebar content
st.sidebar.markdown("##### Example: https://www.transfermarkt.com/malaysia/startseite/verein/15738")
custom_team_url = st.sidebar.text_input("Paste Transfermarkt team URL", placeholder="https://www.transfermarkt.com/...")
use_custom_url = custom_team_url.strip() != ""

selected_league = st.selectbox("Select League", list(LEAGUE_URLS.keys()))
with st.spinner("🔄 Loading Data..."):
    teams = get_teams_by_league(LEAGUE_URLS[selected_league])

if use_custom_url:
    team_url = custom_team_url.strip()
    st.success("✅ Using custom team URL.")
else:
    selected_team = st.selectbox("Select Team", list(teams.keys()))
    team_url = teams[selected_team]

st.markdown(f"🔗 [View on Transfermarkt]({team_url})", unsafe_allow_html=True)
with st.spinner("🔄 Loading Data..."):
    df = scrape_team(team_url)

# === Flatten Nationalities ===
expanded_rows = []
for _, row in df.iterrows():
    for nat in [n.strip() for n in row["Nationality"].split(",")]:
        new_row = row.copy()
        new_row["Nationality"] = nat
        expanded_rows.append(new_row)
df_flat = pd.DataFrame(expanded_rows)

def parse_market_value(val):
    val = val.replace("€", "").lower().strip()
    if val == "-" or val == "":
        return 0
    try:
        return int(float(val.replace("m", "")) * 1_000_000) if "m" in val else int(float(val.replace("k", "")) * 1_000)
    except:
        return 0

df_flat["Market Value Num"] = df_flat["Market Value"].apply(parse_market_value)

# === Sidebar Filters ===
st.sidebar.header("Filter Players")
positions = sorted(df_flat["Position"].dropna().unique())
nations = sorted(df_flat["Nationality"].dropna().unique())
selected_positions = st.sidebar.multiselect("Positions", positions)
selected_nations = st.sidebar.multiselect("Nationalities", nations)

filtered_df = df_flat.copy()
if selected_positions:
    filtered_df = filtered_df[filtered_df["Position"].isin(selected_positions)]
if selected_nations:
    filtered_df = filtered_df[filtered_df["Nationality"].isin(selected_nations)]

# === Network Graph ===

options = ["Name", "Position", "Nationality", "Market Value", "Age"]
source_col = st.selectbox("Select Source Node", options, index=0)
target_col = st.selectbox("Select Target Node", options, index=2)

if source_col != target_col:
    rows = []
    for _, row in filtered_df.iterrows():
        targets = [val.strip() for val in str(row[target_col]).split(",")] if "," in str(row[target_col]) else [row[target_col]]
        for target in targets:
            rows.append({"Source": row[source_col], "Target": target})
    flat_edge_df = pd.DataFrame(rows)

    G = nx.Graph()
    for _, row in flat_edge_df.iterrows():
        G.add_node(row["Source"], type="source")
        G.add_node(row["Target"], type="target")
        G.add_edge(row["Source"], row["Target"])

    net_graph = Network(height="900px", width="100%", bgcolor="white")
    net_graph.from_nx(G)

    for node in net_graph.nodes:
        if node["id"] in flat_edge_df["Source"].values:
            match = filtered_df[filtered_df[source_col] == node["id"]].iloc[0]
            node["title"] = f"{source_col}: {node['id']}\nPosition: {match['Position']}\nAge: {match['Age']}\nNationality: {match['Nationality']}\nMarket Value: {match['Market Value']}"
            node["color"] = "orange"
            node["shape"] = "star"
        else:
            if target_col == "Nationality":
                flag_url = country_to_flag_url(node["id"])
                if flag_url:
                    node["shape"] = "image"
                    node["image"] = flag_url
                    node["label"] = node["id"]
                else:
                    node["color"] = "#00fa9a"
                    node["shape"] = "ellipse"
            elif target_col == "Position":
                node["color"] = "#00bfff"
                node["shape"] = "diamond"
            else:
                node["color"] = "#ff69b4"
                node["shape"] = "box"
        node["size"] = 30
        node["font"] = {"size": 20, "bold": True, "color": "black"}

    tmp_path = os.path.join(tempfile.gettempdir(), "network.html")
    net_graph.write_html(tmp_path, local=False)
    with open(tmp_path, 'r', encoding='utf-8') as f:
        st.components.v1.html(f.read(), height=900, scrolling=True)
else:
    st.warning("⚠️ Source and Target cannot be the same.")


if not df.empty:
    # === Flatten Nationalities ===
    expanded_rows = []
    for _, row in df.iterrows():
        nationalities = [n.strip() for n in row["Nationality"].split(",")]
        for nat in nationalities:
            row_copy = row.copy()
            row_copy["Nationality"] = nat
            expanded_rows.append(row_copy)
    df_flat = pd.DataFrame(expanded_rows)

    # === Market Value Processing ===
    def parse_market_value(val):
        if val == "-" or val == "":
            return 0
        val = val.replace("€", "").lower().strip()
        if "m" in val:
            return int(float(val.replace("m", "")) * 1_000_000)
        elif "k" in val:
            return int(float(val.replace("k", "")) * 1_000)
        else:
            try:
                return int(val)
            except:
                return 0

    def market_tier(value):
        if value >= 100_000_000:
            return "Tier 1: >€100M"
        elif value >= 50_000_000:
            return "Tier 2: €50M - €100M"
        elif value >= 10_000_000:
            return "Tier 3: €10M - €50M"
        elif value >= 5_000_000:
            return "Tier 4: €5M - €10M"
        elif value < 5_000_000:
            return "Tier 5: <€5M"
        else:
            return "Unknown"

    df_flat["Market Value Num"] = df_flat["Market Value"].apply(parse_market_value)
    df_flat["Market Tier"] = df_flat["Market Value Num"].apply(market_tier)

    # === Age Grouping ===
    def age_group(age):
        try:
            age = int(age)
            if age < 24:
                return "15-23"
            elif age < 30:
                return "24-29"
            elif age < 35:
                return "30-34"
            else:
                return "35+"
        except:
            return "Unknown"

    df_flat["Age Group"] = df_flat["Age"].apply(age_group)

    # === Count Tables ===
    nationality_count = df_flat["Nationality"].value_counts().reset_index()
    nationality_count.columns = ["Nationality", "Count"]
    #nationality_count["Nationality"] = nationality_count["Nationality"].apply(lambda x: f"{emoji_flag_mapping.get(x, '')} {x}")

    # Recalculate Market Value and Age Group on original df
    df["Market Value Num"] = df["Market Value"].apply(parse_market_value)
    df["Market Tier"] = df["Market Value Num"].apply(market_tier)
    df["Age Group"] = df["Age"].apply(age_group)

    # Now calculate counts based on original df
    position_count = df["Position"].value_counts().reset_index()
    position_count.columns = ["Position", "Count"]

    market_tier_count = df["Market Tier"].value_counts().reset_index()
    market_tier_count.columns = ["Market Tier", "Count"]

    age_group_count = df["Age Group"].value_counts().reset_index()
    age_group_count.columns = ["Age Group", "Count"]
    
        # === Tabs: Analytics ===
    st.subheader("📊 Squad Composition")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔍 Overall", "🌍 Nationality", "🏃 Position", "💰 Market Value", "🎂 Age Group"])

    with tab1:
        selected_columns = ["Name", "Position", "Date of Birth", "Age", "Nationality", "Market Value"]
        df1 = df[selected_columns].reset_index(drop=True)
        df1.index += 1
        df1.index.name = "No"
        st.dataframe(df1)

    with tab2:
        # st.markdown(nationality_count.to_html(escape=False, index=False), unsafe_allow_html=True)
        #st.dataframe(nationality_count)
        df2 = nationality_count.reset_index(drop=True)
        df2.index += 1
        df2.index.name = "No"
        st.dataframe(df2)

    with tab3:
        df3 = position_count.reset_index(drop=True)
        df3.index += 1
        df3.index.name = "No"
        st.dataframe(df3)

    with tab4:
        df4 = market_tier_count.reset_index(drop=True)
        df4.index += 1
        df4.index.name = "No"
        st.dataframe(df4)

    with tab5:
        df5 = age_group_count.reset_index(drop=True)
        df5.index += 1
        df5.index.name = "No"
        st.dataframe(df5)
