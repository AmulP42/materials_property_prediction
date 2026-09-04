## Materials Property Prediction

This project is an end-to-end machine learning pipeline for predicting material properties using the Materials Project database. The pipeline ingests roughly 163k inorganic materials, stores them in a cloud data lake, and trains an XGBoost model to predict three properties: band gap, formation energy, and bulk modulus. All three properties were benchmarked against their corresponding Matbench leaderboard.

## Results

| Property | Our MAE (XGBoost) | Matbench SOTA | SOTA Model |
|---|---|---|---|
| Band Gap | 0.473 eV | 0.156 eV | coGN | 
| Formation Energy | 0.175 eV/atom | 0.017 eV/atom | coGN | 
| Bulk Modulus | 0.081 log₁₀(GPa) | 0.049 log₁₀(GPa) | coNGN |

Despite only using composition-based Magpie descriptors, the XGBoost model still achieves competetive results with SOTA models trained on crystal structure inputs. 

## Notebooks

| Notebook | Description |
|---|---|
| `01_eda.ipynb` | Data validation, property distributions, UMAP compositional space, periodic table heatmaps |
| `02_features.ipynb` | Generation of Magpie descriptors via matminer, feature matrix construction |
| `03_train.ipynb` | XGBoost training per property, MLflow experiment tracking, SHAP feature importance, Matbench comparison |

---

## Key Findings

### EDA 
Visualizations reveal that Band Gap is bimodally distributed with metals at ~0 eV and insulators at 2-6 eV as to be expected. Bulk modulus data is sparse, with only ~13k out of the 163k materials having DFT-computed values. UMAP projection graphs reveal clear patterns through compositional clustering. We see transition-metal compounds (materials with small band gaps) group separately from oxides and halides (materials with large band gaps). 

### Feature Importance via SHAP Analysis
The SHAP Analysis confirmed that our model successfully learned the underlying physics of our data. 

**Band Gap** — d-orbital valence electron count (`mean NdValence`) is the strongest suppressor of band gap because transition-metal-rich compounds are pushed toward zero. Elemental ground-state band gap (`mean GSbandgap`) is the strongest positive predictor. This makes sense because compounds built from insulating elements tend to be insulators themselves.

**Formation Energy** — electronegativity deviation (`avg_dev Electronegativity`) dominates by a wide margin. High spread in electronegativity across elements strongly predicts negative, or stable, formation energy. Materials with high spread in electronegativity across their constituent elements are consistently predicted to have more negative formation energies. This is the most physically interpretable result of the three.

**Bulk Modulus** — mean ground-state volume per atom (`mean GSvolume_pa`) is the top feature. This is a simple physical relation being that compact, dense materials are stiffer. Mean melting temperature is the second strongest predictor. Materials with high melting points tend to have strong interatomic bonds, thus resisting compression.

Across all three properties, SHAP confirms the model learned physically meaningful relationships.

## Benchmarking
Our model's strongest result was Bulk Modulus, with a MAE of 0.081 $log_{10}$(GPa) compared to the SOTA result of 0.049 $log_{10}$(GPa). Band Gap, on the other hand, was the weakest predictor. This is expected because Band Gap is known to be highly sensitive to crystal structure, which was not an input into our model.

## Setup

**Requirements:** Python 3.10+, [uv](https://github.com/astral-sh/uv), Materials Project API key

```bash
git clone https://github.com/AmulP42/materials_property_prediction
cd materials_property_prediction
make setup
```

Copy `.env.example` to `.env` and fill in the necessary credentials:

```
MP_API_KEY=
DB_HOST=
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_PORT=5432
S3_BUCKET_NAME=
```

**Initialize the database:**
```bash
make init_db
```

**Run ingestion:**
```bash
make data
```

**Start MLflow UI:**
```bash
make mlflow
```

Then open `notebooks/` in Jupyter and run in order.

---

## Stack

- **Data:** Materials Project API (`mp-api`), AWS S3, AWS RDS PostgreSQL
- **Features:** matminer Magpie descriptors (145-dimensional composition features)
- **Models:** XGBoost, MLflow for experiment tracking
- **Interpretability:** SHAP TreeExplainer
- **Benchmark:** [Matbench v0.1](https://matbench.materialsproject.org/)
- **Environment:** uv, pyproject.toml

---
