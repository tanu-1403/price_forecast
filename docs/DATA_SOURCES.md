# How to retrieve every kind of data this project needs

Legend: ✔ = I read the source page during this project (facts below are from it);
✘ = I could **not** verify it, so treat as a lead and check yourself.
All external data goes in `data/external/<name>/` and is joined to the price panel on
**`(district, date)`** (daily variables) or **`(district, year)`** (yearly variables) or **`(commodity, year)`** (e.g. MSP).

## 0. Rules for every added variable
1. **Release lag / leakage.** Use only what was known on the forecast day. Annual production for 2023 is published months or years later; do not attach it to January 2023 prices. Weather: for a forecast made on day *t*, use weather up to *t* (or an official forecast issued at *t*), never the actual weather after *t*.
2. **Resolution mismatch.** Prices are district-day. Weather grids and soil rasters must be summarised per district (average over the district area, or the nearest grid cell as a first approximation). Static variables (soil) stay static; do not treat them as daily.
3. **Keep the raw download untouched** in `data/external/<name>/raw/`; write derived tables beside it.
4. **Record** source URL, download date, licence and citation in `docs/SOURCES_LOG.md`.

---
## 1. Prices (done for 2015 – 20 Apr 2026)  ✔
Source: Hugging Face `DHIVAKARNAIDUSUNKARI/mandi-india-daily-prices-2001-2026`; original data from Agmarknet via data.gov.in "Variety-wise Daily Market Prices" (GODL-India); compiled by Manas Khandelwal. 26 yearly Parquet files, 853 MB. Columns: State, District, Market, Commodity, Variety, Grade, Arrival_Date, Min_Price, Max_Price, Modal_Price, Commodity_Code. **No arrivals.**

Steps (Windows, from the repo folder):
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m src.run_pipeline
```
This downloads only 2015+ files into `data\raw\` (12 of the 26 files, if there is one file per year), filters, cleans, aggregates and writes the report.
**Already downloaded the files earlier?** Reuse them (no re-download):
```
python -m src.run_pipeline --raw-dir "C:\Users\DELL\Documents\PROJECT 4\output\mandi_prices\raw"
```
(The earlier script used `local_dir=...\raw`, which creates `data\mandi_daily_by_year\...` inside it, the relative path this code should expect; untested.)

### The missing months (21 Apr 2026 → today)
The dataset ends 20 Apr 2026 for these crops. Options, best first:
1. **Check the dataset again later**: the repo was last updated recently; new yearly/partial files may appear. Re-run `python -m src.run_pipeline --force`.
2. **Agmarknet portal** (`agmarknet.gov.in`) price & arrival reports. ✘ I do not know whether it allows date ranges or state+commodity downloads; the report you downloaded earlier was an all-India 3-day summary, which is unusable. If you find a report giving **per-market, per-day rows**, save it as CSV in `data/raw/agmarknet_manual/` and tell me; I will add a small importer (same columns as above).
3. **data.gov.in** variety-wise resource page ✔ lists the dataset; your API key attempt did not work. ✘ I have not confirmed whether the API serves the history. Revoke the exposed key first.
4. **Daily collection from today** (any working source) so the gap stops growing.
Until one works, models can be trained and **back-tested** on 2015 – Apr 2026, but a forecast for *today* is not valid.

---
## 2. Rainfall (daily)  ✔ (IMD) / ✔ (NASA POWER)
**Option A – IMD gridded rainfall (official, preferred for India).**
- Source: India Meteorological Department, Pune (`imdpune.gov.in`, gridded data download page). Daily rainfall **0.25° × 0.25°, 1901 – present**, binary `.grd` files, one per year. Maximum/minimum temperature are on a coarser **1.0° grid, 1951 – present**.
- Retrieval (code sketches below are untested: my sandbox has no internet): Python package `imdlib` (`pip install imdlib`), which downloads and reads these files. Sketch (check the `imdlib` documentation for the exact signature):
```python
import imdlib as imd
imd.get_data('rain', 2015, 2025, fn_format='yearwise', file_dir='data/external/imd')   # download
ds = imd.open_data('rain', 2015, 2025, 'yearwise', 'data/external/imd')                # read
xr = ds.get_xarray()                                                                    # xarray Dataset
# repeat with 'tmax' and 'tmin'
```
- To district: simplest first version = value at the grid cell nearest each district's main market (needs latitude/longitude per district, which you can type into a small CSV). Better version = average all grid cells inside the district polygon (needs a Maharashtra district boundary file, e.g. from Survey of India or DataMeet's public maps repository ✘ not verified).
- Problems: the IMD server is sometimes unavailable (noted by users of the R package ✔); the most recent months can lag; temperature at 1° (~110 km) is very coarse for a district; very small values/zero rain are real zeros, not missing.

**Option B – NASA POWER (easy API, no login).**
- ✔ Daily point API: `https://power.larc.nasa.gov/api/temporal/daily/point` with `parameters`, `community=AG`, `latitude`, `longitude`, `start=YYYYMMDD`, `end=YYYYMMDD`, `format=CSV`. No authentication. Data from **1981 onward**, resolution about **0.5° × 0.625°**; up to 20 parameters per point request.
- Useful parameters: `PRECTOTCORR` (rain, mm/day), `T2M`, `T2M_MAX`, `T2M_MIN` (°C), `RH2M` (humidity %).
```python
import requests, pandas as pd
url = "https://power.larc.nasa.gov/api/temporal/daily/point"
p = dict(parameters="PRECTOTCORR,T2M,T2M_MAX,T2M_MIN", community="AG",
         latitude=18.52, longitude=73.86, start="20150101", end="20261119", format="JSON")
j = requests.get(url, params=p, timeout=120).json()
df = pd.DataFrame(j["properties"]["parameter"]).rename_axis("date").reset_index()   # needs `pip install requests`
```
(Pune coordinates shown as an example; do one request per district point.) Missing values are coded `-999` and must be set to NaN.
- Use A for rainfall accuracy in India; B is a good first source because it is easy and complete. Do not mix them inside one model without checking they agree.

**Derived variables** (built later, from past days only): cumulative rainfall since 1 June, 30-day rainfall total, monsoon-season total, dry-spell length, heat-wave indicator (e.g. Tmax above a chosen threshold).

---
## 3. Temperature (daily) — see section 2 (same sources: IMD `tmax`/`tmin`, NASA `T2M*`).

---
## 4. Soil (static)  ✔ SoilGrids / ✘ Soil Health Card
- **SoilGrids (ISRIC)** ✔: 250 m global maps of 14 properties (pH, organic carbon, bulk density, coarse fragments, sand, silt, clay, CEC, nitrogen, …) at six depth intervals; licence CC-BY 4.0. Download GeoTIFF tiles from `https://files.isric.org/soilgrids/latest/data/`. ISRIC states its REST API is **temporarily paused**, so use the GeoTIFF files. Average the raster inside each district (or sample at market locations) → one row per district.
- **Soil Health Card** (Government of India scheme) ✔ exists, with district-level nutrient status; ✘ I could not confirm a bulk-download route. Look on the Soil Health Card portal of the Department of Agriculture & Farmers Welfare.
- Join: `district` only. These are **time-invariant**, so they add information about *which district*, not about *which day*; use them to explain differences between districts, not daily changes.

---
## 5. Crop area, production, yield (yearly)  ✔
- Source: Directorate of Economics & Statistics, Ministry of Agriculture (`desagri.gov.in`) → Statistics → **Area, Production & Yield (APY)** → **District-wise** (also State-wise, National). Season-wise for wheat (rabi) and maize (kharif/rabi).
- IndiaStat Districts ✔ lists district-wise wheat and maize area/production/yield tables for Maharashtra by year (some content may need a subscription ✘).
- Problems: yearly only; published with a lag of a year or more (see rule 1); district boundaries change (new districts, renamed ones).
- Join: `(district, crop_year)`. For forecasting year *Y*, use year *Y−1* or earlier.

---
## 6. Minimum Support Price (MSP)  ✔
- Source: DES "Latest Minimum Support Price (MSP) Statement" on `desagri.gov.in`; the Commission for Agricultural Costs & Prices; Government press releases.
- Retrieval: type a small table `data/external/msp.csv` with columns `commodity, season_year, msp_rs_per_quintal, announced_date`. From the Agmarknet summary you downloaded: **2026-27 MSP: Wheat ₹2,585, Maize ₹2,410 per quintal**. Fill earlier years from the official statement (do not copy from memory).
- Join: `(commodity, date)` using the MSP **in force on that date** (a step function that changes on the announcement/effective date). Useful derived variable: market price ÷ MSP.

---
## 7. Arrivals (quantity brought to market)  ✔ not in the price dataset
The price dataset has no arrivals. Agmarknet's own reports show "Arrival (Metric Tonnes)" (your downloaded summary had it), so arrivals exist at source. ✘ Whether a per-market, per-day arrivals history can be downloaded is unverified; this is the first thing to check on the Agmarknet portal. If found, join on `(market, date)` and then aggregate arrivals to the district (sum), which would also make an arrivals-weighted district price possible.

---
## 8. Wholesale vs retail prices  ✘
Retail and wholesale price monitoring is run by the Department of Consumer Affairs (price monitoring portal) ✘ I could not verify access or the data layout in this project. DES also publishes **farm harvest prices** ✔ (listed on `desagri.gov.in`). Check availability and district coverage before planning around it.

---
## 9. Summary table
| Variable | Source | Frequency | Space | Join key | Main risk |
|---|---|---|---|---|---|
| Modal price | HF/Agmarknet ✔ | daily | mandi → district | – | gaps, few mandis, ends Apr 2026 |
| Rainfall | IMD ✔ / NASA POWER ✔ | daily | 0.25° / 0.5°×0.625° | district, date | server gaps, grid→district |
| Temperature | IMD ✔ / NASA POWER ✔ | daily | 1° / 0.5°×0.625° | district, date | coarse grid |
| Soil | SoilGrids ✔ / SHC ✘ | static | 250 m / district | district | static, not daily |
| Area/production | DES APY ✔ | yearly | district | district, year | release lag, boundary changes |
| MSP | DES / CACP ✔ | per season | national | commodity, date | manual entry |
| Arrivals | Agmarknet ✘ | daily | mandi | market, date | download route unverified |
| Wholesale/retail | Consumer Affairs ✘ | daily | centres | – | access unverified |
