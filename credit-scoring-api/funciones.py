"""
Funciones auxiliares para los notebooks de credit scoring.
Extraidas de modelo_combinado.ipynb para mantener el notebook limpio.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    confusion_matrix, roc_auc_score, roc_curve,
    precision_recall_curve, precision_score, recall_score, f1_score,
)
from sklearn.utils import resample


# =============================================================================
# DATA CLEANING
# =============================================================================

def sanitize_df(df):
    """Clean data for modeling: replace inf, convert extension dtypes."""
    df = df.copy()
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.replace({pd.NA: np.nan})

    for col in df.columns:
        dtype_str = str(df[col].dtype)
        if 'Int' in dtype_str or 'UInt' in dtype_str or 'Float' in dtype_str:
            df[col] = df[col].astype('float64')
        elif dtype_str in ['boolean', 'bool']:
            df[col] = df[col].astype('float64')
        elif dtype_str == 'string':
            df[col] = df[col].astype('object')
    return df


def to_num(s):
    """Convert strings '1.234.567,89' -> 1234567.89"""
    s = s.astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
    return pd.to_numeric(s, errors='coerce')


def safe_ratio(df, num_col, den_col, out_col, make_flag=True):
    """Vectorized, inf-safe ratio: df[out_col] = num/den with NaN when den bad."""
    a = pd.to_numeric(df[num_col], errors='coerce')
    b = pd.to_numeric(df[den_col], errors='coerce')

    bad_den = b.isna() | (b == 0) | ~np.isfinite(b)
    bad_num = a.isna() | ~np.isfinite(a)

    res = a.divide(b)
    res = res.mask(bad_den | bad_num)

    df[out_col] = res
    if make_flag:
        df[f"flag_{out_col}den0"] = (b.isna() | (b == 0)).astype('Int64')
    return df


# =============================================================================
# TARGET ENGINEERING
# =============================================================================

def create_future_target(df, months_ahead_min=6, months_ahead_max=12):
    """Para cada fila, busca la calificacion 6-12 meses en el futuro."""
    df = df.copy()
    df['TARGET_FUTURE_RATING'] = None
    df['TARGET_FUTURE_DATE'] = None
    df['TARGET_MONTHS_AHEAD'] = None
    df['TARGET_STATUS'] = None

    print(f"Buscando calificaciones {months_ahead_min}-{months_ahead_max} meses adelante...")

    for idx, row in df.iterrows():
        if idx % 1000 == 0:
            print(f"  {idx:,}/{len(df):,} ({idx/len(df)*100:.0f}%)", end='')

        rut = row['RUT']
        current_date = row['FECHA_dt']
        if pd.isna(current_date):
            df.at[idx, 'TARGET_STATUS'] = 'invalid_date'
            continue

        min_date = current_date + pd.DateOffset(months=months_ahead_min)
        max_date = current_date + pd.DateOffset(months=months_ahead_max)

        future_obs = df[
            (df['RUT'] == rut) &
            (df['FECHA_dt'] > current_date) &
            (df['FECHA_dt'] >= min_date) &
            (df['FECHA_dt'] <= max_date)
        ]

        if len(future_obs) == 0:
            df.at[idx, 'TARGET_STATUS'] = 'no_future'
            continue

        future_row = future_obs.iloc[0]
        months_diff = (future_row['FECHA_dt'].year - current_date.year) * 12 + \
                      (future_row['FECHA_dt'].month - current_date.month)

        df.at[idx, 'TARGET_FUTURE_RATING'] = future_row['CALIFICACION']
        df.at[idx, 'TARGET_FUTURE_DATE'] = future_row['FECHA_dt']
        df.at[idx, 'TARGET_MONTHS_AHEAD'] = months_diff
        df.at[idx, 'TARGET_STATUS'] = 'found'

    print(f"Completado")

    mapping = {'4': 1, '5': 1, '1A': 0, '1C': 0, '2A': 0, '2B': 0, '3': 1}
    df['DEFAULT_FUTURE'] = df['TARGET_FUTURE_RATING'].map(mapping)
    df['DEFAULT_CURRENT'] = df['CALIFICACION'].map(mapping)

    return df


# =============================================================================
# METRICS & SCORING
# =============================================================================

def ks_stat(y_true, y_score):
    """Calculate KS statistic."""
    data = pd.DataFrame({'y': y_true, 'p': y_score}).sort_values('p')
    cum_good = (1 - data['y']).cumsum() / (1 - data['y']).sum()
    cum_bad  = data['y'].cumsum() / data['y'].sum()
    return float(np.max(np.abs(cum_bad - cum_good)))


def proba_to_points(p, pdo=50, base_score=600, base_odds=20):
    """Convert probabilities to credit scores (0-1500)."""
    factor = pdo / np.log(2)
    offset = base_score - factor * np.log(base_odds)
    p = np.clip(p, 1e-6, 1 - 1e-6)
    odds = (1 - p) / p
    return np.clip(offset + factor * np.log(odds), 0, 1500)


def assign_rating(score):
    """Mapea credit score a categoria de calificacion BCU.
    Categorias (sin 1A que fue descartada por falta de info de garantias):
      1C - Capacidad de pago fuerte
      2A - Capacidad de pago adecuada
      2B - Capacidad de pago con problemas potenciales
      3  - Capacidad de pago comprometida
      4  - Capacidad de pago muy comprometida
      5  - Irrecuperables
    """
    if score >= 1000: return '1C'
    elif score >= 800: return '2A'
    elif score >= 600: return '2B'
    elif score >= 400: return '3'
    elif score >= 200: return '4'
    else: return '5'


def evaluate_model(name, y_train, train_pred, y_test, test_pred, extra_params=None):
    """Evaluate model with Youden's J optimal threshold."""
    fpr, tpr, thresholds = roc_curve(y_test, test_pred)
    j_scores = tpr - fpr
    optimal_idx = np.argmax(j_scores)
    optimal_thr = float(thresholds[optimal_idx])
    test_pred_binary = (test_pred >= optimal_thr).astype(int)

    results = {
        'Strategy': name,
        'Train_AUC': roc_auc_score(y_train, train_pred),
        'Test_AUC': roc_auc_score(y_test, test_pred),
        'Train_KS': ks_stat(y_train, train_pred),
        'Test_KS': ks_stat(y_test, test_pred),
        'Test_Threshold': optimal_thr,
        'Test_Precision': precision_score(y_test, test_pred_binary, zero_division=0),
        'Test_Recall': recall_score(y_test, test_pred_binary, zero_division=0),
        'Test_F1': f1_score(y_test, test_pred_binary, zero_division=0),
        'Overfit_Gap': roc_auc_score(y_train, train_pred) - roc_auc_score(y_test, test_pred)
    }
    if extra_params:
        results.update(extra_params)
    return results


# =============================================================================
# VISUALIZATION — EDA
# =============================================================================

def create_histograms_for_all_variables(df, figsize_per_plot=(4, 3), bins=30, cols_per_row=4,
                                        include_stats=True, exclude_columns=None):
    """Crea histogramas para todas las variables numericas de un DataFrame."""
    numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
    if exclude_columns:
        numeric_columns = [c for c in numeric_columns if c not in exclude_columns]
    if not numeric_columns:
        print("No hay columnas numericas")
        return
    n_cols = min(cols_per_row, len(numeric_columns))
    n_rows = (len(numeric_columns) + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(figsize_per_plot[0]*n_cols, figsize_per_plot[1]*n_rows))
    if len(numeric_columns) == 1:
        axes = [axes]
    elif n_rows == 1:
        axes = axes if isinstance(axes, (list, np.ndarray)) else [axes]
    else:
        axes = axes.flatten()
    for i, col in enumerate(numeric_columns):
        ax = axes[i]
        data = df[col].dropna()
        if len(data) > 0:
            try:
                ax.hist(data, bins=bins, alpha=0.7, edgecolor='black', color='steelblue')
            except (ValueError, IndexError):
                try:
                    ax.hist(data, bins='auto', alpha=0.7, edgecolor='black', color='steelblue')
                except (ValueError, IndexError):
                    ax.text(0.5, 0.5, f'Low variance\n({data.nunique()} unique)',
                            ha='center', va='center', transform=ax.transAxes, fontsize=8)
            if include_stats:
                ax.set_title(f"{col}\n(n={len(data)}, mu={data.mean():.2f})", fontsize=8)
            else:
                ax.set_title(col, fontsize=8)
        else:
            ax.text(0.5, 0.5, f'Sin datos\n{col}', ha='center', va='center', transform=ax.transAxes)
        ax.tick_params(axis='both', labelsize=7)
        ax.grid(True, alpha=0.3)
    for i in range(len(numeric_columns), len(axes)):
        axes[i].set_visible(False)
    plt.tight_layout(pad=2.0)
    plt.show()


def plot_class_imbalance(y, title='Distribucion de la variable objetivo'):
    """Grafico de barras horizontales con conteo y % por clase."""
    counts = y.value_counts().sort_index()
    pcts = y.value_counts(normalize=True).sort_index() * 100
    labels = [f'{int(k)} — {"Default" if k == 1 else "No Default"}' for k in counts.index]

    fig, ax = plt.subplots(figsize=(8, 3))
    bars = ax.barh(labels, counts.values, color=['steelblue', 'coral'])
    for bar, count, pct in zip(bars, counts.values, pcts.values):
        ax.text(bar.get_width() + max(counts) * 0.01, bar.get_y() + bar.get_height()/2,
                f'{count:,} ({pct:.1f}%)', va='center', fontsize=11)
    ax.set_xlabel('Cantidad')
    ax.set_title(title, fontsize=13, fontweight='bold')
    ax.set_xlim(0, max(counts) * 1.2)
    plt.tight_layout()
    plt.show()


def plot_correlation_heatmap(df, target_col='DEFAULT_FUTURE', top_n=20):
    """Heatmap triangular de las top-N features mas correlacionadas con el target."""
    numeric_df = df.select_dtypes(include='number')
    corr = numeric_df.corr()
    if target_col in corr.columns:
        top_features = corr[target_col].abs().sort_values(ascending=False).head(top_n + 1).index.tolist()
    else:
        top_features = corr.abs().mean().sort_values(ascending=False).head(top_n).index.tolist()

    corr_sub = corr.loc[top_features, top_features]
    mask = np.triu(np.ones_like(corr_sub, dtype=bool), k=1)

    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(corr_sub, mask=mask, annot=True, fmt='.2f', cmap='RdBu_r',
                center=0, vmin=-1, vmax=1, square=True, ax=ax,
                annot_kws={'size': 7}, linewidths=0.5)
    ax.set_title(f'Correlacion entre top {top_n} features (+ target)', fontsize=13, fontweight='bold')
    plt.xticks(rotation=45, ha='right', fontsize=8)
    plt.yticks(fontsize=8)
    plt.tight_layout()
    plt.show()


# =============================================================================
# VISUALIZATION — MODEL DIAGNOSTICS
# =============================================================================

def plot_roc_pr_curves(models_dict, y_true):
    """Curvas ROC y Precision-Recall lado a lado."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    for name, y_proba in models_dict.items():
        fpr, tpr, _ = roc_curve(y_true, y_proba)
        auc_val = roc_auc_score(y_true, y_proba)
        ax1.plot(fpr, tpr, label=f'{name} (AUC={auc_val:.4f})', linewidth=2)

        prec, rec, _ = precision_recall_curve(y_true, y_proba)
        ax2.plot(rec, prec, label=f'{name}', linewidth=2)

    ax1.plot([0, 1], [0, 1], 'k--', alpha=0.5, label='Random')
    ax1.set_xlabel('False Positive Rate'); ax1.set_ylabel('True Positive Rate')
    ax1.set_title('Curva ROC', fontsize=13, fontweight='bold')
    ax1.legend(loc='lower right'); ax1.grid(True, alpha=0.3)

    baseline = y_true.mean() if hasattr(y_true, 'mean') else np.mean(y_true)
    ax2.axhline(y=baseline, color='k', linestyle='--', alpha=0.5, label=f'Baseline ({baseline:.3f})')
    ax2.set_xlabel('Recall'); ax2.set_ylabel('Precision')
    ax2.set_title('Curva Precision-Recall', fontsize=13, fontweight='bold')
    ax2.legend(loc='upper right'); ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()


def plot_calibration_curve(models_dict, y_true, n_bins=10):
    """Diagrama de confiabilidad."""
    from sklearn.calibration import calibration_curve as cal_curve

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot([0, 1], [0, 1], 'k--', alpha=0.5, label='Calibracion perfecta')

    for name, y_proba in models_dict.items():
        fraction_pos, mean_pred = cal_curve(y_true, y_proba, n_bins=n_bins, strategy='uniform')
        ax.plot(mean_pred, fraction_pos, 's-',
                label=f'{name}', linewidth=2, markersize=6)

    ax.set_xlabel('Probabilidad predicha')
    ax.set_ylabel('Proporcion de positivos observada')
    ax.set_title('Curva de Calibracion', fontsize=13, fontweight='bold')
    ax.legend(loc='upper left'); ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


# =============================================================================
# MODEL TRAINING INFRASTRUCTURE
# =============================================================================

def replace_inf(X):
    """Replace inf/-inf with NaN (for imputation downstream)."""
    X = np.array(X, dtype=np.float64, copy=True)
    X[~np.isfinite(X)] = np.nan
    return X


def clip_inf(X):
    """Replace inf/-inf and clip to float32 range."""
    X = np.array(X, dtype=np.float64, copy=True)
    X[~np.isfinite(X)] = 0.0
    max32 = np.finfo(np.float32).max
    np.clip(X, -max32, max32, out=X)
    return X


from sklearn.base import BaseEstimator, TransformerMixin


class OutlierClipTransformer(BaseEstimator, TransformerMixin):
    """Sklearn-compatible transformer: clips features to bounds learned from fit data.

    Methods:
        'percentile' (default): clip to P1/P99
        'iqr': clip to Q1 - 1.5*IQR / Q3 + 1.5*IQR
        'zscore': clip to mean ± 3*std
    """

    def __init__(self, method='percentile', lower_percentile=1, upper_percentile=99):
        self.method = method
        self.lower_percentile = lower_percentile
        self.upper_percentile = upper_percentile

    def fit(self, X, y=None):
        X_arr = np.asarray(X, dtype=np.float64)
        if self.method == 'percentile':
            self.lo_ = np.nanpercentile(X_arr, self.lower_percentile, axis=0)
            self.hi_ = np.nanpercentile(X_arr, self.upper_percentile, axis=0)
        elif self.method == 'iqr':
            q1 = np.nanpercentile(X_arr, 25, axis=0)
            q3 = np.nanpercentile(X_arr, 75, axis=0)
            iqr = q3 - q1
            self.lo_ = q1 - 1.5 * iqr
            self.hi_ = q3 + 1.5 * iqr
        elif self.method == 'zscore':
            mu = np.nanmean(X_arr, axis=0)
            std = np.nanstd(X_arr, axis=0)
            std[std == 0] = 1
            self.lo_ = mu - 3 * std
            self.hi_ = mu + 3 * std
        return self

    def transform(self, X):
        X_arr = np.array(X, dtype=np.float64, copy=True)
        np.clip(X_arr, self.lo_, self.hi_, out=X_arr)
        return X_arr


# Alias for backwards compatibility
WinsorizationTransformer = OutlierClipTransformer


def muestra_estratificada(outlier_names, transform_configs, feature_set_names,
                          resampling_configs, n_sample=60, random_state=42):
    """Sample ~n_sample combos ensuring every axis level appears >= 5 times."""
    import random as rng_mod
    rng = rng_mod.Random(random_state)
    all_combos = []
    for o in outlier_names:
        for tf_name, use_yj in transform_configs:
            for fs_name in feature_set_names:
                for rs_name, rs_cls, rs_kw in resampling_configs:
                    all_combos.append((o, tf_name, use_yj, fs_name, rs_name, rs_cls, rs_kw))
    if n_sample >= len(all_combos):
        return all_combos
    selected = set()
    axes = {'o': [c[0] for c in all_combos], 'tf': [c[1] for c in all_combos],
            'fs': [c[3] for c in all_combos], 'rs': [c[4] for c in all_combos]}
    axis_idx = {'o': 0, 'tf': 1, 'fs': 3, 'rs': 4}
    for ak, av in axes.items():
        idx_pos = axis_idx[ak]
        for val in sorted(set(av)):
            cands = [i for i, c in enumerate(all_combos) if c[idx_pos] == val]
            already = len([i for i in selected if i in cands])
            needed = max(0, 5 - already)
            avail = [i for i in cands if i not in selected]
            rng.shuffle(avail)
            for i in avail[:needed]: selected.add(i)
    remaining = [i for i in range(len(all_combos)) if i not in selected]
    rng.shuffle(remaining)
    while len(selected) < n_sample and remaining: selected.add(remaining.pop())
    return [all_combos[i] for i in sorted(selected)]


def build_pipeline(classifier, needs_imputer, use_winsor=False, outlier_method='percentile',
                   use_yj=False, yj_standardize=True, use_scaler=False,
                   resampler_cls=None, resampler_kwargs=None):
    """Build sklearn/imblearn Pipeline with an already-instantiated classifier.

    Pipeline order: clean_inf → imputer → outlier_clip → yj → clip → scaler → resampler → classifier

    Args:
        outlier_method: 'percentile' (P1/P99), 'iqr' (Q1-1.5*IQR), or 'zscore' (mean±3*std)
    """
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import PowerTransformer, FunctionTransformer, StandardScaler
    from sklearn.pipeline import Pipeline
    from imblearn.pipeline import Pipeline as ImbPipeline

    steps = []
    if needs_imputer:
        steps.append(('clean_inf', FunctionTransformer(replace_inf)))
        steps.append(('imputer', SimpleImputer(strategy='median')))
    if use_winsor:
        steps.append(('outlier_clip', OutlierClipTransformer(method=outlier_method)))
    if use_yj:
        steps.append(('yj', PowerTransformer(method='yeo-johnson', standardize=yj_standardize)))
        steps.append(('clip', FunctionTransformer(clip_inf)))
    if use_scaler:
        steps.append(('scaler', StandardScaler()))
    if resampler_cls is not None:
        steps.append(('resampler', resampler_cls(**resampler_kwargs)))
    steps.append(('classifier', classifier))
    if resampler_cls is not None:
        return ImbPipeline(steps)
    return Pipeline(steps)


def train_and_evaluate_model(strategy_name, X_tr, y_tr, X_te, y_te, pipeline,
                             param_grid, cv, groups_tr=None, n_iter=None,
                             search_type='grid', n_jobs=-1,
                             results_list=None, metadata_fn=None):
    """Unified: GridSearchCV or RandomizedSearchCV + calibration + metrics.

    Args:
        param_grid: dict of hyperparameters to search
        cv: number of cross-validation folds
        n_iter: number of iterations (only for search_type='random')
        search_type: 'grid' (exhaustive) or 'random' (sampled)
    """
    from sklearn.model_selection import GridSearchCV, RandomizedSearchCV, GroupKFold
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.frozen import FrozenEstimator
    from sklearn.pipeline import Pipeline

    cv_splitter = GroupKFold(n_splits=cv)

    if search_type == 'grid':
        search = GridSearchCV(
            pipeline, param_grid, scoring='roc_auc',
            cv=cv_splitter, n_jobs=n_jobs, refit=True
        )
    else:
        search = RandomizedSearchCV(
            pipeline, param_grid, n_iter=n_iter or 50, scoring='roc_auc',
            cv=cv_splitter, n_jobs=n_jobs, random_state=42, refit=True
        )

    search.fit(X_tr, y_tr, groups=groups_tr)
    best_pipe = search.best_estimator_

    n_combos = len(search.cv_results_['mean_test_score'])
    print(f"  Evaluadas {n_combos} combinaciones ({search_type})")

    # Calibration: strip resampler, freeze to prevent refitting
    try:
        pasos_cal = [(n, s) for n, s in best_pipe.named_steps.items()
                     if not hasattr(s, 'fit_resample')]
        pipe_cal = Pipeline(pasos_cal) if len(pasos_cal) < len(best_pipe.named_steps) else best_pipe
        cal = CalibratedClassifierCV(FrozenEstimator(pipe_cal), method='isotonic', cv=5)
        cal.fit(X_tr, y_tr)
        train_pred = cal.predict_proba(X_tr)[:, 1]
        test_pred = cal.predict_proba(X_te)[:, 1]
    except (ValueError, RuntimeError) as e:
        print(f"     Calibration failed ({e.__class__.__name__}), using uncalibrated model")
        cal = best_pipe
        tr_proba = best_pipe.predict_proba(X_tr)
        te_proba = best_pipe.predict_proba(X_te)
        train_pred = tr_proba[:, 1] if tr_proba.shape[1] > 1 else tr_proba[:, 0]
        test_pred = te_proba[:, 1] if te_proba.shape[1] > 1 else te_proba[:, 0]

    results = evaluate_model(strategy_name, y_tr, train_pred, y_te, test_pred)
    results['CV_AUC'] = round(search.best_score_, 4)
    results['Best_Params'] = search.best_params_

    if metadata_fn:
        results.update(metadata_fn(best_pipe))

    if results_list is not None:
        results_list.append(results)

    print(f"  Test AUC: {results['Test_AUC']:.4f}  |  CV AUC: {results['CV_AUC']:.4f}"
          f"  |  Overfit: {results['Overfit_Gap']:.4f}")

    return results, cal, best_pipe
