# -*- coding: utf-8 -*-
"""
Congestion Prediction Model
Predict subway congestion as auxiliary input to SeatScore
"""

import pickle
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split


class CongestionPredictor:
    """Build and evaluate congestion prediction models for Line 2"""

    def __init__(self, data_processed_dir="data_processed", random_state=42):
        self.data_processed_dir = Path(data_processed_dir)
        self.models_dir = self.data_processed_dir / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.random_state = random_state
        self.models = {}
        self.feature_columns = []

    def load_data(self):
        """Load preprocessed master dataset"""
        print("=" * 70)
        print("LOADING DATA")
        print("=" * 70)

        csv_path = self.data_processed_dir / "master_dataset.csv"
        df = pd.read_csv(csv_path, encoding="utf-8-sig")

        print(f"Loaded: {len(df):,} rows x {len(df.columns)} columns")
        return df

    def prepare_features(self, df):
        """Build feature matrix and target vector"""
        print("\n" + "=" * 70)
        print("PREPARING FEATURES")
        print("=" * 70)

        # --- time features ---
        time_feats = [
            "hour", "hour_sin", "hour_cos", "time_minutes",
            "is_morning_rush", "is_evening_rush", "is_night",
        ]

        # --- spatial ---
        spatial_feats = ["cumulative_distance"]

        # --- type one-hot ---
        df["is_boarding"] = (df["type"] == "boarding").astype(int)
        df["is_alighting"] = (df["type"] == "alighting").astype(int)

        # --- station one-hot (top 30) ---
        top_stations = df["station_normalized"].value_counts().head(30).index
        for stn in top_stations:
            df[f"stn_{stn}"] = (df["station_normalized"] == stn).astype(int)
        station_feats = [c for c in df.columns if c.startswith("stn_")]

        self.feature_columns = (
            time_feats + spatial_feats + ["is_boarding", "is_alighting"] + station_feats
        )

        df_clean = df[self.feature_columns + ["count"]].dropna()
        print(f"Features: {len(self.feature_columns)}")
        print(f"Samples after dropna: {len(df_clean):,}")
        print(f"Target range: [{df_clean['count'].min():.0f}, {df_clean['count'].max():.0f}]")
        print(f"Target mean:  {df_clean['count'].mean():.1f}")

        X = df_clean[self.feature_columns]
        y = df_clean["count"]
        return X, y

    def _evaluate(self, name, model, X_train, y_train, X_test, y_test):
        """Calculate metrics and store results"""
        ytr_pred = model.predict(X_train)
        yte_pred = model.predict(X_test)

        result = {
            "model": model,
            "train_rmse": np.sqrt(mean_squared_error(y_train, ytr_pred)),
            "test_rmse":  np.sqrt(mean_squared_error(y_test,  yte_pred)),
            "train_mae":  mean_absolute_error(y_train, ytr_pred),
            "test_mae":   mean_absolute_error(y_test,  yte_pred),
            "train_r2":   r2_score(y_train, ytr_pred),
            "test_r2":    r2_score(y_test,  yte_pred),
        }
        self.models[name] = result

        print(f"\n  Train RMSE: {result['train_rmse']:.2f}   Test RMSE: {result['test_rmse']:.2f}")
        print(f"  Train MAE:  {result['train_mae']:.2f}   Test MAE:  {result['test_mae']:.2f}")
        print(f"  Train R2:   {result['train_r2']:.4f}   Test R2:   {result['test_r2']:.4f}")

        return result

    def train_linear_regression(self, X_train, y_train, X_test, y_test):
        print("\n" + "=" * 70)
        print("LINEAR REGRESSION")
        print("=" * 70)
        lr = LinearRegression()
        lr.fit(X_train, y_train)
        return self._evaluate("linear_regression", lr, X_train, y_train, X_test, y_test)

    def train_random_forest(self, X_train, y_train, X_test, y_test):
        print("\n" + "=" * 70)
        print("RANDOM FOREST")
        print("=" * 70)
        rf = RandomForestRegressor(
            n_estimators=100,
            max_depth=15,
            min_samples_split=10,
            random_state=self.random_state,
            n_jobs=-1,
        )
        print("Fitting...")
        rf.fit(X_train, y_train)

        result = self._evaluate("random_forest", rf, X_train, y_train, X_test, y_test)

        # Feature importance
        imp = pd.DataFrame({
            "feature": self.feature_columns,
            "importance": rf.feature_importances_,
        }).sort_values("importance", ascending=False)

        print("\n  Top 10 features:")
        for _, row in imp.head(10).iterrows():
            print(f"    {row['feature']:<30} {row['importance']:.4f}")

        result["feature_importance"] = imp
        return result

    def save_models(self):
        print("\n" + "=" * 70)
        print("SAVING MODELS")
        print("=" * 70)
        for name, data in self.models.items():
            path = self.models_dir / f"{name}.pkl"
            with open(path, "wb") as f:
                pickle.dump(data, f)
            print(f"  Saved: {path}")

        feat_path = self.models_dir / "feature_columns.pkl"
        with open(feat_path, "wb") as f:
            pickle.dump(self.feature_columns, f)
        print(f"  Saved: {feat_path}")

    def run_full_pipeline(self):
        """Execute full modeling pipeline"""
        print("=" * 70)
        print("METROPY CONGESTION PREDICTION PIPELINE")
        print("=" * 70)

        df = self.load_data()
        X, y = self.prepare_features(df)

        print("\n" + "=" * 70)
        print("TRAIN-TEST SPLIT (80/20)")
        print("=" * 70)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=self.random_state
        )
        print(f"Train: {len(X_train):,}  |  Test: {len(X_test):,}")

        self.train_linear_regression(X_train, y_train, X_test, y_test)
        self.train_random_forest(X_train, y_train, X_test, y_test)
        self.save_models()

        # Comparison table
        print("\n" + "=" * 70)
        print("MODEL COMPARISON")
        print("=" * 70)
        print(f"\n{'Model':<22} {'Test RMSE':<12} {'Test MAE':<12} {'Test R2':<10}")
        print("-" * 56)
        for name, m in self.models.items():
            print(f"{name:<22} {m['test_rmse']:<12.2f} {m['test_mae']:<12.2f} {m['test_r2']:<10.4f}")

        print("\nNote: These models predict congestion as input to SeatScore,")
        print("      NOT as the final goal.")
        print("      SeatScore(c) = sum[ D(s) * T(s->dest) * w(c,s) ]")

        return self.models


if __name__ == "__main__":
    predictor = CongestionPredictor(data_processed_dir="../data_processed")
    models = predictor.run_full_pipeline()
    print("\nNext: Implement SeatScore decision model")
