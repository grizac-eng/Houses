# Greece House Sales Trends — Streamlit App

## What it does
- Upload an Excel with house sales
- Choose aggregation: **Month / Quarter / Year**
- Computes:
  - **# of sales**
  - **Total traded surface (sqm)** (main area, optionally main+aux)
  - **Old/New mix** with dynamic bucket:  
    - `pre_1990` (editable threshold)  
    - `new_last5y` (built within last N years relative to sale year; editable)  
    - `mid_age`  
    - `unknown` (missing build year)

## Install
```bash
pip install streamlit pandas openpyxl plotly numpy
```

## Run
```bash
streamlit run app.py
```

## Notes for your example file
The defaults match your Greek column names, including:
- Ημερομηνία Συμβολαίου (sale date)
- Έτος Κατασκευής (year built)
- Eπιφάνεια Κύριων Χώρων (main sqm)
- Επιφάνεια Βοηθητικών Χώρων (aux sqm, optional)
