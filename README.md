# Greece House Sales Trends — Streamlit App (Built-in years)

## What changed vs v1
- You can bundle multiple yearly Excel files inside the repository under `data/`
- The UI lets the user select which years to analyze (no upload needed)

## Run locally
```bash
pip install streamlit pandas openpyxl plotly numpy
streamlit run app.py
```

## Deploy on Streamlit Cloud
- Push `app.py`, `requirements.txt`, and the `data/` folder to GitHub
- In Streamlit Cloud, set the main file to `app.py`

## Repo structure
```
.
├── app.py
├── requirements.txt
└── data
    ├── mhtrwo-ax-met-ak-2017.xlsx
    ├── ...
    └── mhtrwo-ax-met-ak-2026.xlsx
```

## Note on storage
If the dataset grows big, you can switch to a compact format (Parquet) later, but Excel-in-repo is simplest to start.
