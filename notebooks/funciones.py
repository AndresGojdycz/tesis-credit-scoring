"""
Funciones auxiliares para los notebooks de credit scoring.
Extraidas de modelo_combinado.ipynb para mantener el notebook limpio.
"""

import re
import textwrap
import time
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.ticker import FuncFormatter, MaxNLocator
from sklearn.feature_selection import RFECV
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


def safe_ratio(df, num_col, den_col, out_col, make_flag=False):
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
    """Para cada fila, busca el balance siguiente de la misma empresa entre 6 y 12 meses
    despues y la calificacion asociada a ese balance.

    Define la POBLACION de estudio (empresas que siguen presentando balances y son
    calificadas en el ciclo siguiente). El target del trabajo (default sostenido en
    [t+7, t+18]) se recalcula despues, en la celda del target del notebook.
    """
    df = df.copy()
    df['TARGET_FUTURE_RATING'] = None
    df['TARGET_FUTURE_DATE'] = None
    df['TARGET_MONTHS_AHEAD'] = None
    df['TARGET_STATUS'] = None

    for idx, row in df.iterrows():

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


def proba_to_points(p, pdo=50, base_score=600):
    """Convert probabilities to credit scores (0-1500)."""
    factor = pdo / np.log(2)
    p = np.clip(p, 1e-6, 1 - 1e-6)
    odds = (1 - p) / p
    return np.clip(base_score + factor * np.log(odds), 0, 1500)


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


def evaluate_model(name, y_train, train_pred, y_test, test_pred, extra_params=None,
                   threshold=None):
    """Evaluate model (metricas de ranking). Precision/recall/F1 solo si se pasa un
    umbral derivado sin usar el test; sin umbral quedan NaN. (El fallback del umbral optimo
    sobre el test se elimino el 2026-09-23: hallazgo #23 — el punto de operacion
    se deriva una sola vez, por CV anidada, en la celda de seleccion.)"""
    if threshold is None or not np.isfinite(threshold):
        optimal_thr, prec, rec, f1v = np.nan, np.nan, np.nan, np.nan
    else:
        optimal_thr = float(threshold)
        test_pred_binary = (test_pred >= optimal_thr).astype(int)
        prec = precision_score(y_test, test_pred_binary, zero_division=0)
        rec = recall_score(y_test, test_pred_binary, zero_division=0)
        f1v = f1_score(y_test, test_pred_binary, zero_division=0)

    results = {
        'Strategy': name,
        'Train_AUC': roc_auc_score(y_train, train_pred),
        'Test_AUC': roc_auc_score(y_test, test_pred),
        'Train_KS': ks_stat(y_train, train_pred),
        'Test_KS': ks_stat(y_test, test_pred),
        'Test_Threshold': optimal_thr,
        'Test_Precision': prec,
        'Test_Recall': rec,
        'Test_F1': f1v,
        'Overfit_Gap': roc_auc_score(y_train, train_pred) - roc_auc_score(y_test, test_pred)
    }
    if extra_params:
        results.update(extra_params)
    return results


def compute_cv_threshold(pipeline, X_tr, y_tr, groups_tr, cv=5):
    """Umbral de maxima separacion KS por validacion cruzada (sin usar el test).

    En cada fold se entrena el pipeline sobre el fold-train y se busca el
    umbral que maximiza J = TPR - FPR en el hold-out; se devuelve el promedio
    de los `cv` umbrales (CV clasica: estadisticos por fold, sin concatenar
    predicciones entre folds)."""
    from sklearn.model_selection import GroupKFold
    from sklearn.base import clone

    def seleccionar_filas(obj, idx):
        return obj.iloc[idx] if hasattr(obj, 'iloc') else obj[idx]

    thresholds = []
    splitter = GroupKFold(n_splits=cv)
    for tr_idx, va_idx in splitter.split(X_tr, y_tr, groups=np.asarray(groups_tr)):
        mdl = clone(pipeline)
        mdl.fit(seleccionar_filas(X_tr, tr_idx), seleccionar_filas(y_tr, tr_idx))
        proba_va = mdl.predict_proba(seleccionar_filas(X_tr, va_idx))[:, 1]
        fpr, tpr, thr = roc_curve(seleccionar_filas(y_tr, va_idx), proba_va)
        thresholds.append(float(thr[np.argmax(tpr - fpr)]))
    return float(np.mean(thresholds))


def evaluar_modelo(name, modelo, X_tr, X_te, y_tr, y_te, res):
    """Resumen de un modelo entrenado (metricas de ranking) en formato dict.

    `res` viene de `train_and_evaluate_model` y aporta CV_AUC. El umbral operativo
    y las metricas de punto de operacion (test_threshold / precision / recall / F1)
    se completan despues, en la celda de seleccion, con el mismo criterio para todos
    los candidatos (maxima separacion KS, promedio por fold de la CV anidada); aqui quedan en NaN.
    """
    proba_tr = modelo.predict_proba(X_tr)[:, 1]
    proba_te = modelo.predict_proba(X_te)[:, 1]
    train_auc = roc_auc_score(y_tr, proba_tr)
    test_auc = roc_auc_score(y_te, proba_te)
    test_ks_val = ks_stat(y_te, proba_te)

    return {
        'Model': name,
        'cv_auc': res['CV_AUC'],
        'test_auc': round(test_auc, 4),
        'test_ks': round(test_ks_val, 4),
        'test_threshold': np.nan,
        'test_precision': np.nan,
        'test_recall': np.nan,
        'test_f1': np.nan,
        'train_auc': round(train_auc, 4),
        'overfit_gap': round(train_auc - test_auc, 4),
    }


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


def plot_class_imbalance(y, title='Distribucion de la variable objetivo', colors=('steelblue', 'coral')):
    """Grafico de barras horizontales con conteo y % por clase."""
    counts = y.value_counts().sort_index()
    pcts = y.value_counts(normalize=True).sort_index() * 100
    labels = [f'{int(k)} — {"Default" if k == 1 else "No Default"}' for k in counts.index]

    fig, ax = plt.subplots(figsize=(8, 3))
    bars = ax.barh(labels, counts.values, color=list(colors))
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


def run_preprocessing_grid(model_name, base_classifier, param_grid,
                           datos_outlier, conjuntos_features,
                           configs_transformacion, configs_resampling,
                           y_train, y_test, grupos_train,
                           use_scaler=False, n_sample=120,
                           n_iter=10, cv=5, n_jobs=-1,
                           decile_fn=None, woe_fn=None):
    """Run preprocessing grid: test all combos of (outlier × transform × features × resampling),
    do RandomizedSearchCV for hyperparameters, and select best combo by CV_AUC.

    Returns: (all_results list, best_combo dict)
    """
    import time
    from sklearn.metrics import roc_auc_score

    outlier_names = list(datos_outlier.keys())
    fs_names = list(conjuntos_features.keys())

    sampled = muestra_estratificada(
        outlier_names, configs_transformacion, fs_names,
        configs_resampling, n_sample=n_sample)

    all_results = []
    best_cv_auc = 0
    best_combo = None

    n = len(sampled)
    t0 = time.time()

    for i, (outlier_name, tf_name, use_yj, fs_name, rs_name, rs_cls, rs_kw) in enumerate(sampled, 1):
        # Transformaciones discretas + YJ no tienen sentido: saltar
        if tf_name in ('Deciles', 'WoE') and use_yj:
            continue

        # Chi2 fue computado sobre deciles -> solo aplicable cuando transform=Deciles.
        # (Las features Chi2-selected pueden o no ser predictivas bajo otras
        # representaciones; el test estadistico solo es valido bajo la representacion
        # con la que se computo.)
        if fs_name.startswith('Chi2') and tf_name != 'Deciles':
            continue

        strategy = f"{outlier_name} + {tf_name} + {fs_name} + {rs_name}"

        X_tr, X_te, needs_imputer = datos_outlier[outlier_name]
        feats = conjuntos_features[fs_name]
        X_tr_fs, X_te_fs = X_tr[feats], X_te[feats]

        # Aplicar discretizacion por deciles si corresponde
        if tf_name == 'Deciles' and decile_fn is not None:
            X_tr_fs, X_te_fs = decile_fn(X_tr_fs, X_te_fs)
            needs_imputer = False  # decile_fn ya imputa internamente
        elif tf_name == 'WoE' and woe_fn is not None:
            X_tr_fs, X_te_fs = woe_fn(X_tr_fs, X_te_fs)
            needs_imputer = False  # woe_fn ya imputa internamente

        pipe = build_pipeline(
            base_classifier.__class__(**base_classifier.get_params()),
            needs_imputer=needs_imputer,
            use_yj=use_yj, use_scaler=use_scaler,
            resampler_cls=rs_cls,
            resampler_kwargs=rs_kw if rs_kw else None)

        elapsed = time.time() - t0
        eta = (elapsed / i * (n - i)) if i > 1 else 0
        print(f"\n[{i}/{n}] {strategy}  (ETA: {eta/60:.0f} min)")

        grupos_cv = grupos_train.loc[X_tr_fs.index]

        try:
            res, modelo_entrenado, best_pipe = train_and_evaluate_model(
                strategy, X_tr_fs, y_train, X_te_fs, y_test, pipe,
                param_grid=param_grid, cv=cv, search_type='random',
                n_iter=n_iter, n_jobs=n_jobs, groups_tr=grupos_cv,
                results_list=all_results)
        except Exception as e:
            print(f"  FAILED: {e}")
            continue

        if res['CV_AUC'] > best_cv_auc:
            best_cv_auc = res['CV_AUC']
            best_combo = {
                'strategy': strategy, 'outlier': outlier_name,
                'transform': tf_name, 'use_yj': use_yj,
                'needs_imputer': needs_imputer,
                'features': fs_name, 'resampling': rs_name,
                'rs_cls': rs_cls, 'rs_kw': rs_kw,
                'modelo_entrenado': modelo_entrenado, 'best_pipe': best_pipe,
                'feats': feats,
                'cv_auc': res['CV_AUC'], 'test_auc': res['Test_AUC'],
                'best_params': res.get('Best_Params', {}),
            }

    total = time.time() - t0
    print(f"\n{'='*80}")
    print(f"{model_name} Grid: {len(all_results)}/{n} combos in {total/60:.1f} min")
    if best_combo:
        print(f"Best (CV AUC): {best_combo['strategy']}")
        print(f"  CV={best_combo['cv_auc']:.4f}, Test={best_combo['test_auc']:.4f}")

    return all_results, best_combo


def analyze_grid_results(all_results, model_name):
    """Show top 3 combinations by CV AUC, ordenadas. Devuelve el DataFrame completo."""
    df = pd.DataFrame(all_results).sort_values('CV_AUC', ascending=False).reset_index(drop=True)

    # Solo metricas de ranking: el grid compara combos por CV_AUC; el punto de
    # operacion (precision/recall/F1) se deriva una sola vez en la celda de seleccion.
    cols = ['Strategy', 'CV_AUC', 'Train_AUC', 'Test_AUC', 'Overfit_Gap', 'Test_KS']
    cols = [c for c in cols if c in df.columns]
    print(f"{'='*120}")
    print(f"{model_name}: TOP 3 COMBINATIONS (by CV AUC)")
    print(f"{'='*120}")
    print(df[cols].head(3).round(4).to_string(index=False))

    return df


def build_pipeline(classifier, needs_imputer,
                   use_yj=False, yj_standardize=True, use_scaler=False,
                   resampler_cls=None, resampler_kwargs=None):
    """Build sklearn/imblearn Pipeline with an already-instantiated classifier.

    Pipeline order: clean_inf → imputer → yj → clip → scaler → resampler → classifier
    """
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import PowerTransformer, FunctionTransformer, StandardScaler
    from sklearn.pipeline import Pipeline
    from imblearn.pipeline import Pipeline as ImbPipeline

    steps = []
    if needs_imputer:
        steps.append(('clean_inf', FunctionTransformer(replace_inf)))
        steps.append(('imputer', SimpleImputer(strategy='median')))
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
                             results_list=None, metadata_fn=None,
                             use_cv_threshold=False, calibrate=False):
    """Unified: GridSearchCV or RandomizedSearchCV + (opcional calibration) + metrics.

    Args:
        param_grid: dict of hyperparameters to search
        cv: number of cross-validation folds
        n_iter: number of iterations (only for search_type='random')
        search_type: 'grid' (exhaustive) or 'random' (sampled)
        use_cv_threshold: if True, umbral de maxima separacion KS por validacion cruzada
            (promedio por fold) sobre training, en lugar del test.
        calibrate: if True, wrap best estimator in CalibratedClassifierCV (isotonic).
            Default False — el modelo se usa sin calibracion.
    """
    from sklearn.model_selection import GridSearchCV, RandomizedSearchCV, GroupKFold
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

    if calibrate:
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.frozen import FrozenEstimator
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
    else:
        # Sin calibracion: usar el best_pipe directamente
        cal = best_pipe
        tr_proba = best_pipe.predict_proba(X_tr)
        te_proba = best_pipe.predict_proba(X_te)
        train_pred = tr_proba[:, 1] if tr_proba.shape[1] > 1 else tr_proba[:, 0]
        test_pred = te_proba[:, 1] if te_proba.shape[1] > 1 else te_proba[:, 0]

    cv_thr = None
    if use_cv_threshold and groups_tr is not None:
        try:
            cv_thr = compute_cv_threshold(best_pipe, X_tr, y_tr, groups_tr, cv=cv)
        except Exception as e:
            print(f"     CV threshold failed ({e.__class__.__name__}), falling back to test-based")

    results = evaluate_model(strategy_name, y_tr, train_pred, y_te, test_pred,
                             threshold=cv_thr)
    results['CV_AUC'] = round(search.best_score_, 4)
    results['Best_Params'] = search.best_params_

    if metadata_fn:
        results.update(metadata_fn(best_pipe))

    if results_list is not None:
        results_list.append(results)

    print(f"  Test AUC: {results['Test_AUC']:.4f}  |  CV AUC: {results['CV_AUC']:.4f}"
          f"  |  KS: {results['Test_KS']:.4f}  |  F1: {results['Test_F1']:.4f}"
          f"  |  Prec: {results['Test_Precision']:.4f}  |  Rec: {results['Test_Recall']:.4f}"
          f"  |  Overfit: {results['Overfit_Gap']:.4f}")

    return results, cal, best_pipe

# =============================================================================
# FEATURE ENGINEERING
# =============================================================================


def apply_feature_engineering(df):
    """Aplica ratios financieros y lags temporales a un DataFrame."""
    df = df.copy()
    
 # Ratios financieros
    # Distinguimos ingresos brutos vs netos: la mayoria de los margenes y la
    # rotacion usan brutos (denominador "ventas totales"), mientras que el
    # margen neto usa netos (post bonificaciones). La cobertura de intereses
    # es la habitual: Resultado Operativo / Intereses Perdidos.
    ing_brutos = "Total Ingresos Operativos" if "Total Ingresos Operativos" in df.columns else None
    ing_netos = "Total Ingresos Operativos Netos" if "Total Ingresos Operativos Netos" in df.columns else None
    # Fallback: si solo existe una columna, usarla para ambos roles
    ing_brutos = ing_brutos or ing_netos
    ing_netos = ing_netos or ing_brutos
    int_col = "Intereses Perdidos."

    if "Resultado Operativo" in df.columns and int_col in df.columns:
        safe_ratio(df, "Resultado Operativo", int_col, "Cobertura_de_intereses")

    ratio_defs = [
        ("TOTAL PASIVO",     "TOTAL PATRIMONIO", "Relacion_deuda_patrimonio"),
        ("TOTAL ACTIVO",     "TOTAL PATRIMONIO", "Multiplicador"),
        ("Resultado Neto",   "TOTAL ACTIVO",     "ROA"),
        ("Resultado Neto",   "TOTAL PATRIMONIO", "ROE"),
        ("Total Activo Corriente",       "Total Pasivo Corriente",  "Ratio_Corriente"),
        ("Sub-total - Disponibilidades", "Total Pasivo Corriente",  "Ratio_Efectivo"),
        ("TOTAL PASIVO",              "TOTAL ACTIVO", "Deuda_sobre_Activos"),
        ("TOTAL PATRIMONIO",          "TOTAL ACTIVO", "Ratio_Patrimonio"),
    ]
    # Margenes y rotacion usan ingresos BRUTOS
    if ing_brutos:
        ratio_defs += [
            ("Resultado Bruto",              ing_brutos, "Margen_Bruto"),
            ("Resultado Operativo",          ing_brutos, "Margen_Operativo"),
            ("Gastos  Ad.y Ventas.",         ing_brutos, "Ratio_GAV"),
            ("Exportaciones",                ing_brutos, "Ratio_Exportaciones"),
            (ing_brutos,                     "TOTAL ACTIVO", "Rotacion_Activos"),
        ]
    # Margen neto usa ingresos NETOS (post bonificaciones)
    if ing_netos:
        ratio_defs.append(("Resultado Neto", ing_netos, "Margen_Neto"))
    
    for num, den, out in ratio_defs:
        if num in df.columns and den in df.columns:
            safe_ratio(df, num, den, out)
    
 # Prueba Acida
    ac, bc, pc = "Total Activo Corriente", "Bienes de Cambio", "Total Pasivo Corriente"
    if all(c in df.columns for c in [ac, bc, pc]):
        df["quick_num"] = (pd.to_numeric(df[ac], errors='coerce')
                           - pd.to_numeric(df[bc], errors='coerce'))
        safe_ratio(df, "quick_num", pc, "Prueba_Acida")
        df.drop(columns=["quick_num"], inplace=True)

 # Exposicion crediticia RELATIVA (Central de Riesgos): el importe crudo NO se
 # usa como predictor (coherencia con la exclusion de CALIFICACION, que emana
 # del mismo registro del regulador); se incluye normalizado por el tamano de
 # la empresa: sobre ventas (brutas) y sobre patrimonio.
    if "IMPORTE_MN" in df.columns:
        df["IMPORTE_MN"] = pd.to_numeric(df["IMPORTE_MN"], errors='coerce')
        if ing_brutos:
            safe_ratio(df, "IMPORTE_MN", ing_brutos, "Importe_sobre_Ventas")
        if "TOTAL PATRIMONIO" in df.columns:
            safe_ratio(df, "IMPORTE_MN", "TOTAL PATRIMONIO", "Importe_sobre_Patrimonio")
        df = df.drop(columns=["IMPORTE_MN"])

 # Temporal lags (delta y pct_change vs periodo anterior)
    if 'RUT' in df.columns and 'FECHA_dt' in df.columns:
        df = df.sort_values(['RUT', 'FECHA_dt'])
        # Flag: primera observacion de la empresa en la muestra — sus features
        # temporales no existen (quedan NaN -> mediana). La flag permite al
        # modelo distinguir "sin historial temporal" de un historial real
        # (~33% de la muestra; ver tesis §3.2.1).
        df['primera_observacion'] = (df.groupby('RUT').cumcount() == 0).astype(int)
        lag_items = {
            'Resultado Operativo':          'Res_Op',
            'Resultado Sin Amortizaciones': 'Res_SinAmort',
            'Resultado Neto':               'Res_Neto',
            'Margen_Operativo':             'MgnOp',
            'ROE':                          'ROE',
            '+(gan) -(pérd) Res Periodo':   'Res_Periodo',   # con tilde: agro se renombra igual que empresas (A1)
            'Margen_Neto':                  'MgnNeto',
            'Margen_Bruto':                 'MgnBruto',
            'ROA':                          'ROA',
            'Total Activo Corriente':       'ActCte',
            'TOTAL ACTIVO':                 'Activo',
            'TOTAL PASIVO':                 'Pasivo',
            'TOTAL PATRIMONIO':             'Patrimonio',
        }

        for col, alias in lag_items.items():
            if col not in df.columns:
                continue
            prev = df.groupby('RUT')[col].shift(1)
            df[f'delta_{alias}'] = df[col] - prev
            df[f'pct_chg_{alias}'] = (df[col] - prev) / prev.abs()
    
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    return df


# =============================================================================
# OUTLIER TREATMENT
# =============================================================================


def compute_outlier_limits(X_tr, method):
    """Calcula los limites de outlier treatment desde el conjunto de entrenamiento.

    Devuelve un dict serializable para reaplicar el mismo clipping en produccion.
    Estructura:
        {'method': str, 'columns': list, 'lo': np.array, 'hi': np.array}

    Si method == 'Ninguno' devuelve None (no hay nada que persistir).
    """
    if method == 'Ninguno':
        return None

    if isinstance(X_tr, pd.DataFrame):
        vals_tr = X_tr.values.astype(np.float64)
        columns = list(X_tr.columns)
    else:
        vals_tr = np.asarray(X_tr, dtype=np.float64)
        columns = None

    if method == 'Winsorization':
        lo = np.nanpercentile(vals_tr, 1, axis=0)
        hi = np.nanpercentile(vals_tr, 99, axis=0)
    elif method == 'IQR':
        q1 = np.nanpercentile(vals_tr, 25, axis=0)
        q3 = np.nanpercentile(vals_tr, 75, axis=0)
        iqr = q3 - q1
        lo = q1 - 1.5 * iqr
        hi = q3 + 1.5 * iqr
    elif method == 'Z-score':
        mu = np.nanmean(vals_tr, axis=0)
        std = np.nanstd(vals_tr, axis=0)
        std[std == 0] = 1
        lo = mu - 3 * std
        hi = mu + 3 * std
    else:
        return None

    # Guard para columnas degeneradas (p.ej. dummies 0/1 con IQR=0, donde
    # lo==hi aplanaria la columna a constante): se desactiva el clip.
    with np.errstate(invalid='ignore'):
        degen = ~(hi > lo)
    lo = np.where(degen, -np.inf, lo)
    hi = np.where(degen, np.inf, hi)

    return {'method': method, 'columns': columns, 'lo': lo, 'hi': hi}


def apply_outlier_limits(X, limits):
    """Aplica limites de outlier treatment precomputados a un DataFrame/array X.

    Reaplica el mismo clipping que se uso durante el entrenamiento, alineando
    columnas por nombre si X es DataFrame. Si limits is None devuelve X sin tocar.
    """
    if limits is None:
        return X.copy() if hasattr(X, 'copy') else np.asarray(X).copy()

    lo = np.asarray(limits['lo'], dtype=np.float64)
    hi = np.asarray(limits['hi'], dtype=np.float64)

    if isinstance(X, pd.DataFrame) and limits.get('columns'):
        # Reordenar X segun el orden de columnas con que se calcularon los limites
        X_aligned = X.reindex(columns=limits['columns'])
        vals = X_aligned.values.astype(np.float64)
        clipped = np.clip(vals, lo, hi)
        return pd.DataFrame(clipped, index=X.index, columns=limits['columns'])

    vals = np.asarray(X, dtype=np.float64)
    return np.clip(vals, lo, hi)


def apply_outlier_treatment(X_tr, X_te, method):
    """Aplica tratamiento de outliers. Limites SIEMPRE desde train."""
    if method == 'Ninguno':
        return X_tr.copy(), X_te.copy()
    
    if isinstance(X_tr, pd.DataFrame):
        vals_tr = X_tr.values.astype(np.float64)
        vals_te = X_te.values.astype(np.float64)
    else:
        vals_tr = np.asarray(X_tr, dtype=np.float64)
        vals_te = np.asarray(X_te, dtype=np.float64)
    
    if method == 'Winsorization':
        lo = np.nanpercentile(vals_tr, 1, axis=0)
        hi = np.nanpercentile(vals_tr, 99, axis=0)
    elif method == 'IQR':
        q1 = np.nanpercentile(vals_tr, 25, axis=0)
        q3 = np.nanpercentile(vals_tr, 75, axis=0)
        iqr = q3 - q1
        lo = q1 - 1.5 * iqr
        hi = q3 + 1.5 * iqr
    elif method == 'Z-score':
        mu = np.nanmean(vals_tr, axis=0)
        std = np.nanstd(vals_tr, axis=0)
        std[std == 0] = 1
        lo = mu - 3 * std
        hi = mu + 3 * std
    else:
        return X_tr.copy(), X_te.copy()

    # Guard para columnas degeneradas (lo==hi, p.ej. dummies con IQR=0):
    # sin este guard la columna quedaria constante y perderia toda senal.
    with np.errstate(invalid='ignore'):
        degen = ~(hi > lo)
    lo = np.where(degen, -np.inf, lo)
    hi = np.where(degen, np.inf, hi)

    out_tr = np.clip(vals_tr, lo, hi)
    out_te = np.clip(vals_te, lo, hi)
    
    if isinstance(X_tr, pd.DataFrame):
        return (pd.DataFrame(out_tr, index=X_tr.index, columns=X_tr.columns),
                pd.DataFrame(out_te, index=X_te.index, columns=X_te.columns))
    return out_tr, out_te


# =============================================================================
# FEATURE SELECTION — INFORMATION VALUE (IV)
# =============================================================================


def calc_iv_train(x, y, n_bins=10):
    """Calcula WoE e IV para un vector feature vs target binario.

    WoE = ln(Distr_Good / Distr_Bad) por bin.
    IV  = sum((Distr_Good_i - Distr_Bad_i) * WoE_i).
    """
    mask = ~np.isnan(x)
    x_clean, y_clean = x[mask], y[mask]
    if len(x_clean) < 50 or len(np.unique(x_clean)) < 2:
        return np.nan, None

    try:
        bins = pd.qcut(pd.Series(x_clean).rank(method='first'),
                        n_bins, labels=False, duplicates='drop')
    except ValueError:
        return np.nan, None

    df_b = pd.DataFrame({'bin': bins, 'y': y_clean})
    g = df_b.groupby('bin')['y'].agg(['sum', 'count'])
    g.columns = ['bads', 'total']
    g['goods'] = g['total'] - g['bads']

    total_bads  = g['bads'].sum()
    total_goods = g['goods'].sum()
    if total_bads == 0 or total_goods == 0:
        return np.nan, None

    eps = 1e-6  # evita log(0)
    g['pct_bads']  = g['bads']  / total_bads
    g['pct_goods'] = g['goods'] / total_goods
    g['woe'] = np.log((g['pct_goods'] + eps) / (g['pct_bads'] + eps))
    g['iv_i'] = (g['pct_goods'] - g['pct_bads']) * g['woe']

    return g['iv_i'].sum(), g


def iv_strength(iv):
    if iv < 0.02: return 'Inutil (<0.02)'
    elif iv < 0.1: return 'Debil (0.02-0.1)'
    elif iv < 0.3: return 'Medio (0.1-0.3)'
    elif iv < 0.5: return 'Fuerte (0.3-0.5)'
    else: return 'Sospechoso (>0.5)'


# =============================================================================
# DECILE TRANSFORMER
# =============================================================================


def create_decile_transformer(X_train_ref):
    """Crea una funcion que discretiza features numericos en deciles.
    Fit sobre X_train_ref. La funcion resultante acepta cualquier subset de columnas."""
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import KBinsDiscretizer
    
    num_cols_all = X_train_ref.select_dtypes(include='number').columns.tolist()
    const_cols = [c for c in num_cols_all if X_train_ref[c].nunique(dropna=True) <= 1]
    num_cols = [c for c in num_cols_all if c not in const_cols]
    

    col_transformers = {}
    for c in num_cols:
        imp = SimpleImputer(strategy='median')
        imp.fit(X_train_ref[[c]])
        disc = KBinsDiscretizer(n_bins=10, encode='ordinal', strategy='quantile')
        disc.fit(imp.transform(X_train_ref[[c]]))
        col_transformers[c] = (imp, disc)
    
    def transform(X_tr, X_te):
        """Aplica discretizacion por deciles. Acepta cualquier subset de columnas."""
        results = []
        for X in [X_tr, X_te]:
            df_out = X.copy()
            for c in X.columns:
                if c in col_transformers:
                    imp, disc = col_transformers[c]
                    vals_imp = imp.transform(X[[c]])
                    vals_dec = disc.transform(vals_imp)
                    df_out[c] = vals_dec.ravel()
 # Las columnas no-numericas o constantes se mantienen sin cambio
            results.append(df_out)
        return results[0], results[1]
    
    transform.n_discretizadas = len(num_cols)
    transform.n_constantes_excluidas = len(const_cols)

    # Exponer los transformers por columna (SimpleImputer, KBinsDiscretizer):
    # son objetos sklearn picklables y permiten serializar la discretizacion
    # junto al modelo para reaplicarla exactamente en serving.
    transform.col_transformers = col_transformers

    return transform


# =============================================================================
# WOE TRANSFORMER (Weight of Evidence encoding)
# =============================================================================


def create_woe_transformer(X_train_ref, y_train_ref, n_bins=10, eps=1e-6):
    """Crea una funcion que aplica WoE encoding a features numericos.

    WoE_i = ln((Goods_i / Total_Goods) / (Bads_i / Total_Bads))
    Fit sobre X_train_ref + y_train_ref. Devuelve transform(X_tr, X_te).

    Features con varianza nula o que fallan el binning quedan sin transformar
    (se mantienen como vinieron, sin warning para no spamear el log).
    """
    from sklearn.impute import SimpleImputer

    num_cols_all = X_train_ref.select_dtypes(include='number').columns.tolist()
    const_cols = [c for c in num_cols_all if X_train_ref[c].nunique(dropna=True) <= 1]
    num_cols = [c for c in num_cols_all if c not in const_cols]

    y_arr = np.asarray(y_train_ref).astype(int)

    col_woe_maps = {}
    for c in num_cols:
        imp = SimpleImputer(strategy='median')
        x_imp = imp.fit_transform(X_train_ref[[c]]).ravel()

        # Quantile bins sobre los datos imputados
        try:
            _, edges = pd.qcut(x_imp, n_bins, labels=False, duplicates='drop', retbins=True)
        except ValueError:
            continue

        if len(edges) < 3:
            continue

        edges_safe = edges.astype(float).copy()
        edges_safe[0] = -np.inf
        edges_safe[-1] = np.inf

        bins = pd.cut(x_imp, edges_safe, labels=False, include_lowest=True)

        df_b = pd.DataFrame({'bin': bins, 'y': y_arr})
        g = df_b.groupby('bin')['y'].agg(['sum', 'count'])
        g.columns = ['bads', 'total']
        g['goods'] = g['total'] - g['bads']
        total_bads = max(int(g['bads'].sum()), 1)
        total_goods = max(int(g['goods'].sum()), 1)
        if total_bads == 0 or total_goods == 0:
            continue
        g['woe'] = np.log(
            ((g['goods'] / total_goods) + eps) / ((g['bads'] / total_bads) + eps)
        )
        woe_map = g['woe'].to_dict()

        col_woe_maps[c] = {
            'imputer': imp,
            'edges': edges_safe,
            'woe_map': woe_map,
            'default_woe': 0.0,
        }

    def transform(X_tr, X_te):
        """Aplica WoE encoding. Acepta cualquier subset de columnas."""
        results = []
        for X in [X_tr, X_te]:
            df_out = X.copy()
            for c in X.columns:
                if c in col_woe_maps:
                    info = col_woe_maps[c]
                    vals_imp = info['imputer'].transform(X[[c]]).ravel()
                    bins = pd.cut(vals_imp, info['edges'], labels=False, include_lowest=True)
                    mapped = pd.Series(bins).map(info['woe_map'])
                    df_out[c] = mapped.fillna(info['default_woe']).astype(float).values
            results.append(df_out)
        return results[0], results[1]

    print(f"WoE transformer creado:")
    print(f"  Features encodeadas: {len(col_woe_maps)}")
    print(f"  Constantes excluidas: {len(const_cols)}")
    print(f"  Bins por feature: {n_bins}")

    return transform


def resumen_ventana_calificaciones(calif_mes, rut, mes_inicio, calif_default, orden_calif):
    """Meses calificados, peor categoria y racha maxima en 3/4/5 en [p0, p0+11]."""
    n_obs = peor = racha = racha_max = 0
    for k in range(12):
        c = calif_mes.get((rut, mes_inicio + k))
        if c is None:
            racha = 0                       # mes sin calificacion corta la racha
            continue
        n_obs += 1
        peor = max(peor, orden_calif.get(c, 0))
        racha = racha + 1 if c in calif_default else 0
        racha_max = max(racha_max, racha)
    return n_obs, peor, racha_max


# Etiquetas cortas para ACTIVIDAD_ECONOMICA — Solo para visualizar mejor los graficos
ETIQUETAS_ACTIVIDAD = {
    'EXPLOTACION GANADERA (EXCEPTO LECHERIA)':                 'Ganaderia (excl. lecheria)',
    'EXPLOTACION LECHERA':                                     'Lecheria',
    'CUL.DE PROD.AGRI.EN COMB.CON CRIA DE ANIM. EXPLOT.MIXTA': 'Agricola-ganadera mixta',
    'TRANSPORTE DE CARGA POR CARRETERA':                       'Transporte de carga',
    'MANTENIMIENTO Y REPARACION DE VEHICULOS AUTOMOTORES':     'Talleres mecanicos',
    'OTRAS ACTIVIDADES DE SERVICIOS N.C.P.':                   'Otros servicios n.c.p.',
    'VENTA AL POR MAYOR DE OTROS PRODUCTOS':                   'Mayorista: otros productos',
    'VENTA AL POR MAYOR DE ALIMENTOS, BEBIDAS Y TABACO':       'Mayorista: alimentos y bebidas',
    'VTA. MENOR ALMAC NO ESPECIALI.,DE ALIM.,BEB. TAB':        'Almacenes de alimentos',
    'VTA.X MENOR DE ALIM.,BEB.Y TABACO EN ALMACEN. ESPECIAL.': 'Minorista: alimentos especializ.',
    'VTA.X MENOR DE APARATOS,ARTICUL.Y EQUIPO USO DOMESTIC.':  'Minorista: electrodomesticos',
    'VTA.X MENOR DE ART.DE FERRETE.,PINTUR. Y PROD.DE VIDRIO': 'Ferreterias y pinturerias',
    'VTA.X MENOR DE OTROS PRODUCTOS DE ALMACENES ESPECIALIZ.': 'Minorista: otros especializados',
    'VTA.POR MENOR DE OTROS PROD.EN ALMACENES NO ESPECIALIZ.': 'Minorista: otros no especializ.',
    'OTROS TIPOS DE VTA. AL POR MENOR NO REALIZ. EN ALMACEN.': 'Minorista fuera de almacen',
    'Otros':                                                   'Otras actividades (fuera del top 15)',
}


def etiqueta_corta_actividad(valor, col):
    """Etiqueta legible para los ejes: usa el diccionario si la columna es
    ACTIVIDAD_ECONOMICA; para actividades no mapeadas devuelve el nombre
    capitalizado y recortado a 35 caracteres; otras columnas quedan igual."""
    if col != 'ACTIVIDAD_ECONOMICA':
        return str(valor)
    if valor in ETIQUETAS_ACTIVIDAD:
        return ETIQUETAS_ACTIVIDAD[valor]
    v = str(valor).capitalize()
    return v if len(v) <= 35 else v[:34] + '…'


DIR_FIG = Path('graficos_tesis')

ENFASIS   = '#c0392b'   # riesgo / default: el dato del mensaje
OSCURO    = '#2c3e50'   # serie principal sin connotacion de riesgo
CONTEXTO  = '#BFBFBF'   # lo que no es el enfasis
REFERENCIA = '#7A7A7A'  # promedios y umbrales
GRIS_TXT  = '#555555'
VERDE     = '#1a9850'   # riesgo bajo
COLOR_TRAIN = 'steelblue'  # desarrollo / train — solo para train vs test
COLOR_TEST  = 'coral'      # validacion / test
SEC_RIESGO = ['#fcbba1', '#fb6a4a', '#cb181d', '#67000d']   # secuencial de una tonalidad (ordinal de riesgo)


def formato_coma(x, dec=1):
    """Numero con coma decimal y punto de miles, como en la tesis."""
    s = f'{x:,.{dec}f}'
    return s.replace(',', '§').replace('.', ',').replace('§', '.')


def formato_porcentaje(x, dec=1):
    return formato_coma(100 * x, dec) + '%'


def decimales_necesarios(v, dec_min=0, dec_max=4):
    """Menor cantidad de decimales que representa el valor exacto de la marca (evita rotulos redondeados)."""
    for d in range(dec_min, dec_max + 1):
        if abs(round(v, d) - v) < 1e-9:
            return d
    return dec_max


def eje_porcentaje(ax, axis='y', dec=0):
    eje = ax.yaxis if axis == 'y' else ax.xaxis
    eje.set_major_locator(MaxNLocator(nbins=6, steps=[1, 2, 5, 10]))
    eje.set_major_formatter(FuncFormatter(lambda v, _: formato_coma(100 * v, decimales_necesarios(100 * v, dec)) + '%'))


def eje_decimal_coma(ax, axis='x', dec=2):
    eje = ax.yaxis if axis == 'y' else ax.xaxis
    eje.set_major_locator(MaxNLocator(nbins=7, steps=[1, 2, 5, 10]))
    eje.set_major_formatter(FuncFormatter(lambda v, _: formato_coma(v, decimales_necesarios(v, dec))))


CAJA = dict(facecolor='white', edgecolor='none', pad=1.5)   # fondo para rotulos sobre lineas de referencia


def limpiar_ejes(ax, grid='x'):
    for s in ['top', 'right']:
        ax.spines[s].set_visible(False)
    for s in ['left', 'bottom']:
        ax.spines[s].set_color(CONTEXTO)
    ax.grid(False)
    if grid:
        ax.grid(axis=grid, color='#EEEEEE', linewidth=0.8)
        ax.set_axisbelow(True)
    ax.tick_params(colors=GRIS_TXT, labelsize=9)


def guardar_figura(fig, titulo, subtitulo, caption, archivo, ancho_txt=95):
    """Titulo (mensaje) y subtitulo (contexto) arriba; guarda a 300 dpi.
    El caption (fuente y notas) queda como documentacion en el codigo: desde el 15/11 las figuras de la
    tesis van sin fuente ni notas al pie, por eso no se dibuja."""
    fig.tight_layout()
    h = fig.get_size_inches()[1] * 72   # alto en puntos
    sub = '\n'.join(textwrap.wrap(subtitulo, ancho_txt + 15))
    tit = '\n'.join(textwrap.wrap(titulo, ancho_txt))
    n_sub, n_tit = (sub.count('\n') + 1 if sub else 0), tit.count('\n') + 1
    y_sub = 1 + 6 / h
    y_tit = y_sub + (n_sub * 9.5 * 1.3 + 5) / h
    fig.text(0.01, y_sub, sub, ha='left', va='bottom', fontsize=9.5, color=GRIS_TXT)
    fig.text(0.01, y_tit, tit, ha='left', va='bottom', fontsize=12.5, fontweight='bold', color='#222222')
    if archivo is None:   # graficos exploratorios: se muestran en la notebook, no se guardan
        plt.show()
        return
    ruta = DIR_FIG / archivo
    fig.savefig(ruta, dpi=300, bbox_inches='tight', facecolor='white')
    plt.show()
    print(f'Guardada: {ruta}')


# Nombres legibles de variables (intuitividad: el lector no tiene que descifrar nombres de columnas)
NOMBRES = {
    'Importe_sobre_Patrimonio': 'Deuda bancaria / patrimonio',
    'Importe_sobre_Ventas': 'Deuda bancaria / ventas',
    'Ratio_Patrimonio': 'Patrimonio / activo',
    'Ratio_Corriente': 'Ratio corriente',
    'Ratio_Efectivo': 'Ratio de efectivo',
    'Prueba_Acida': 'Prueba ácida',
    'Deuda_sobre_Activos': 'Deuda / activo',
    'Relacion_deuda_patrimonio': 'Deuda / patrimonio',
    'Cobertura_de_intereses': 'Cobertura de intereses',
    'Multiplicador': 'Multiplicador (activo / patrimonio)',
    'TIPO_SOCIEDAD_Unipersonal': 'Empresa unipersonal',
    'Acreeds. Bancarios MNal.': 'Acreedores bancarios (m/n)',
    'Acreeds. Bancarios MExt.': 'Acreedores bancarios (m/e)',
    'Acreeds. Bancarios': 'Acreedores bancarios',
    'Total Pasivo No Corriente': 'Pasivo no corriente',
    'Total Pasivo Corriente': 'Pasivo corriente',
    'Sub-total - Disponibilidades': 'Disponibilidades',
    'TOTAL PASIVO': 'Pasivo total',
    'TOTAL PATRIMONIO': 'Patrimonio total',
    'Desempleo_var_trimestral': 'Variación del desempleo',
    'Resultado Sin Amortizaciones': 'Resultado sin amortizaciones',
    'ROA': 'ROA', 'ROE': 'ROE',
    'Rotacion_Activos': 'Rotación de activos', 'Margen_Bruto': 'Margen bruto', 'Margen_Operativo': 'Margen operativo',
    'Margen_Neto': 'Margen neto', 'Margen_EBITDA': 'Margen EBITDA',
}
VARIACION = {'MgnOp': 'del margen operativo', 'MgnBruto': 'del margen bruto', 'MgnNeto': 'del margen neto',
             'ActCte': 'del activo corriente', 'Res_Neto': 'del resultado neto', 'Res_Op': 'del resultado operativo',
             'Activo': 'del activo', 'Pasivo': 'del pasivo', 'Patrimonio': 'del patrimonio', 'ROA': 'del ROA',
             'ROE': 'del ROE'}


def nombre_variable(col):
    if col in NOMBRES:
        return NOMBRES[col]
    if col.startswith('delta_'):
        return 'Variación ' + VARIACION.get(col[6:], 'de ' + nombre_variable(col[6:]))
    if col.startswith('pct_chg_'):
        return 'Variación % de ' + nombre_variable(col[8:])
    return col.replace('_', ' ').strip()


TILDES = {'lecheria': 'lechería', 'agricola': 'agrícola', 'agricolas': 'agrícolas', 'ganaderia': 'ganadería',
          'electrodomesticos': 'electrodomésticos', 'ferreterias': 'ferreterías', 'pinturerias': 'pinturerías',
          'almacen': 'almacén', 'textil': 'textil'}


def etiqueta_actividad(a):
    s = etiqueta_corta_actividad(a, 'ACTIVIDAD_ECONOMICA')
    return re.sub(r'[A-Za-z]+', lambda m: (TILDES.get(m.group(0).lower(), m.group(0)).capitalize()
                                          if m.group(0)[0].isupper() else TILDES.get(m.group(0), m.group(0))), s)


def grafico_barras_composicion(etqs, fracs, ns, titulo, subtitulo):
    """Barras horizontales de composicion: la categoria mas frecuente en oscuro, el resto en gris."""
    fracs = np.asarray(fracs, dtype=float)
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(etqs) + 1.2))
    _yy = np.arange(len(etqs))[::-1]
    _imax = int(np.argmax(fracs))
    ax.barh(_yy, fracs, height=0.6, color=[OSCURO if i == _imax else CONTEXTO for i in range(len(etqs))])
    for y_, f_, n_ in zip(_yy, fracs, ns):
        ax.text(f_ + fracs.max() * 0.01, y_, f'{formato_porcentaje(f_)}  (n = {formato_coma(n_, 0)})', va='center', fontsize=8.5, color=GRIS_TXT)
    ax.set_yticks(_yy)
    ax.set_yticklabels(etqs, fontsize=9)
    ax.set_xlim(0, fracs.max() * 1.3)
    eje_porcentaje(ax, 'x')
    ax.set_xlabel('Porcentaje de las observaciones', color=GRIS_TXT)
    ax.tick_params(axis='y', length=0)
    limpiar_ejes(ax, grid='x')
    guardar_figura(fig, titulo, subtitulo, '', None)


def etiqueta_semestre(k):
    return ('1.er sem. ' if k.endswith('S1') else '2.º sem. ') + k[:4]


def formato_eje_symlog(v, _):
    a = abs(v)
    s = '−' if v < 0 else ''
    if a >= 1e6:
        return f'{s}{formato_coma(a / 1e6, decimales_necesarios(a / 1e6, 0, 1))} M'
    return s + formato_coma(a, decimales_necesarios(a, 0, 2))


def formato_adaptativo(v):
    return formato_coma(v, 2) if abs(v) < 100 else formato_coma(v, 0)


def grafico_distribucion_clase(df, target, col, rank=None):
    """Cajas y puntos de `col` por clase del target (solo train)."""
    n0_cls, n1_cls = int((target == 0).sum()), int((target == 1).sum())
    d = pd.DataFrame({'valor': df[col].astype(float), 'clase': target.values}).dropna()
    lo, hi = d['valor'].quantile([0.01, 0.99])
    usa_symlog = max(abs(lo), abs(hi)) > 1000   # partidas en pesos: ordenes de magnitud
    if usa_symlog:
        d['valor_plot'] = d['valor'].clip(lo, hi)
        ylim = None
    else:
        d['valor_plot'] = d['valor']
        q = d.groupby('clase')['valor'].quantile([0.25, 0.75]).unstack()
        iqr = q[0.75] - q[0.25]
        w_lo = min(d.loc[d['clase'] == c, 'valor'].pipe(lambda v: v[v >= q.loc[c, 0.25] - 1.5 * iqr[c]]).min() for c in q.index)
        w_hi = max(d.loc[d['clase'] == c, 'valor'].pipe(lambda v: v[v <= q.loc[c, 0.75] + 1.5 * iqr[c]]).max() for c in q.index)
        pad = 0.12 * (w_hi - w_lo) if w_hi > w_lo else 1.0
        ylim = (w_lo - pad, w_hi + pad)
    datos = [d.loc[d['clase'] == k, 'valor_plot'].values for k in (0, 1)]
    meds = [float(np.median(x)) for x in datos]
    pts = d.sample(min(len(d), 800), random_state=42)
    rng = np.random.default_rng(42)
    colores = [CONTEXTO, ENFASIS]

    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    for k in (0, 1):
        v = pts.loc[pts['clase'] == k, 'valor_plot'].values
        ax.scatter(k + rng.uniform(-0.18, 0.18, len(v)), v, s=5, lw=0, alpha=0.3,
                   color='#9A9A9A' if k == 0 else ENFASIS, zorder=1)
    bp = ax.boxplot(datos, positions=[0, 1], widths=0.45, patch_artist=True, showfliers=False, whis=1.5, zorder=2,
                    medianprops=dict(color='#222222', lw=1.8), whiskerprops=dict(color=GRIS_TXT),
                    capprops=dict(color=GRIS_TXT), boxprops=dict(edgecolor=GRIS_TXT))
    for caja, c in zip(bp['boxes'], colores):
        caja.set_facecolor(c)
        caja.set_alpha(0.85)
    for k, m in enumerate(meds):
        ax.text(k + 0.26, m, formato_adaptativo(m), va='center', ha='left', fontsize=9, color='#222222', fontweight='bold', bbox=CAJA)
    if usa_symlog:
        ax.set_yscale('symlog', linthresh=1)
        ax.yaxis.set_major_formatter(FuncFormatter(formato_eje_symlog))
    else:
        ax.set_ylim(*ylim)
        eje_decimal_coma(ax, 'y', 0)
    ax.set_xticks([0, 1])
    ax.set_xticklabels([f'Sin default\n(n = {formato_coma(n0_cls, 0)})', f'Default\n(n = {formato_coma(n1_cls, 0)})'])
    ax.set_xlim(-0.6, 1.6)
    ax.set_ylabel(nombre_variable(col) + (' (escala logarítmica simétrica)' if usa_symlog else ''), color=GRIS_TXT)
    ax.tick_params(axis='x', length=0)
    limpiar_ejes(ax, grid='y')
    guardar_figura(fig, f'{nombre_variable(col)}: mediana de {formato_adaptativo(meds[0])} en las observaciones sin default y de {formato_adaptativo(meds[1])} '
                   'en las que entran en default',
                   '', '', None)


def log_simetrico(v):
    return np.sign(v) * np.log10(1 + np.abs(v))


def pares_redundantes(X, cols, umbral):
    """Pares con |Spearman| >= umbral sobre los deciles de train (fit solo en train)."""
    dec = create_decile_transformer(X[cols])
    X_dec, _ = dec(X[cols], X[cols])
    rho = X_dec[cols].corr(method='spearman')
    pares = rho.where(np.triu(np.ones(rho.shape, dtype=bool), k=1)).stack()
    return pares[pares.abs() >= umbral].sort_values(key=abs, ascending=False)


def ejecutar_rfecv(name, estimator, X_fit, y, grupos, columnas, cv, step, min_features):

    t0 = time.time()
    rfecv_i = RFECV(
        estimator=estimator, step=step, cv=cv,
        scoring='roc_auc', min_features_to_select=min_features,
        n_jobs=-1, verbose=0,
    )
    rfecv_i.fit(X_fit, y.astype(int), groups=grupos)

    cv_scores_i = np.asarray(rfecv_i.cv_results_['mean_test_score'])
    cv_std_i = np.asarray(rfecv_i.cv_results_['std_test_score'])

    # sklearn ordena cv_results_ de MENOS a MAS features (5, 9, 14, ..., 164); la
    # reconstruccion manual descendente que habia aca invertia la secuencia y
    # el 'optimo' impreso quedaba espejado (9/119/74 en vez de 159/49/94; #21).
    n_feat_seq = [int(n) for n in rfecv_i.cv_results_['n_features']]

    best_idx = int(np.argmax(cv_scores_i))
    chosen_idx = best_idx
    n_target = n_feat_seq[chosen_idx]
    selected = [f for f, s in zip(columnas, rfecv_i.support_) if s]
    assert n_feat_seq[best_idx] == len(selected), (
        f'{name}: el tamano optimo de la curva ({n_feat_seq[best_idx]}) no coincide con support_ ({len(selected)})')

    elapsed = time.time() - t0
    print(f'  {name}:')
    print(f'    Optimo:    {n_feat_seq[best_idx]:3d} feats, AUC={cv_scores_i[best_idx]:.4f} ± {cv_std_i[best_idx]:.4f}')
    print(f'    Tiempo:    {elapsed:.1f}s')

    return {
        'name': name,
        'rfecv': rfecv_i,
        'best_idx': best_idx,
        'best_score': float(cv_scores_i[best_idx]),
        'best_std': float(cv_std_i[best_idx]),
        'best_n': n_feat_seq[best_idx],
        'chosen_idx': chosen_idx,
        'chosen_n': n_target,
        'chosen_score': float(cv_scores_i[chosen_idx]),
        'selected': set(selected),
        'cv_scores': cv_scores_i,
        'cv_std': cv_std_i,
        'n_feat_seq': n_feat_seq,
        'elapsed': elapsed,
    }


def sin_repetidos(xs):
    return list(dict.fromkeys(xs))


def unir_con_y(xs):
    return xs[0] if len(xs) == 1 else ', '.join(xs[:-1]) + ' y ' + xs[-1]


def discretizar_deciles(s, n_bins=10):
    """Discretiza una serie continua en bins por cuantil """
    from sklearn.preprocessing import KBinsDiscretizer
    if s.nunique() < n_bins:
        return pd.factorize(s)[0]
    try:
        disc = KBinsDiscretizer(n_bins=n_bins, encode='ordinal', strategy='quantile')
        return disc.fit_transform(s.values.reshape(-1, 1)).ravel().astype(int)
    except ValueError:
        return pd.factorize(s)[0]


def entropia(x):
    _, counts = np.unique(x, return_counts=True)
    p = counts / counts.sum()
    return -(p * np.log(p + 1e-12)).sum()


def crear_selectores(est_rfecv, scale, grupos, cache_dir):
    import pipeline_cv as pcv
    return {'RFECV': pcv.FeatureSelector('RFECV', estimator=est_rfecv, scale=scale, grupos=grupos, cache_dir=cache_dir),
            'IV': pcv.FeatureSelector('IV', grupos=grupos, cache_dir=cache_dir),
            'Chi2_dec': pcv.FeatureSelector('Chi2', grupos=grupos, cache_dir=cache_dir)}


def precalcular_seleccion(sel, idx, X, y):   # la seleccion de cada fold se calcula una vez y queda en cache
    import pipeline_cv as pcv
    from sklearn.base import clone
    Xf = pcv.MedianImputer().fit(X.iloc[idx]).transform(X.iloc[idx])
    clone(sel).fit(Xf, y.iloc[idx])


def ic_auc_bootstrap(p, y, posiciones, grupos, B=2000, seed=42):
    """IC 95% del AUC en test por bootstrap de empresas (percentiles)."""
    rng = np.random.default_rng(seed); aucs = []
    for _ in range(B):
        idx = np.concatenate([posiciones[grupos[i]] for i in rng.integers(0, len(grupos), len(grupos))])
        if y[idx].min() != y[idx].max():
            aucs.append(roc_auc_score(y[idx], p[idx]))
    return tuple(np.percentile(aucs, [2.5, 97.5]))


def proba_fold_candidato(predicciones_cv, name, k):
    """Prediccion del candidato en el hold-out del fold k de la CV."""
    return predicciones_cv[name][k]


def primera_mayuscula(s):
    return s[:1].upper() + s[1:]


def aplicar_scorecard(scores, defaults, cortes, etiquetas):
    bands_ = np.searchsorted(cortes, scores, side='right')
    return pd.DataFrame({'score': scores,
                         'band': [etiquetas[b] for b in bands_],
                         'default': defaults})


def iv_bandas_scorecard(df_b, etiquetas):
    n_bads = int(df_b['default'].sum())
    n_goods = len(df_b) - n_bads
    iv_ = 0.0
    for label in etiquetas:
        sub = df_b[df_b['band'] == label]
        bads_b = int(sub['default'].sum())
        goods_b = len(sub) - bads_b
        if bads_b == 0 or goods_b == 0:
            return np.nan  # banda pura o vacia: IV no computable
        iv_ += (goods_b / n_goods - bads_b / n_bads) * np.log((goods_b / n_goods) / (bads_b / n_bads))
    return iv_


# score: se leen como medida relativa de riesgo, no como frecuencia esperada.
# score = 600 + (50/ln2)*ln((1-p)/p)  <=>  p = 1 / (1 + 2**((score-600)/50))
def score_a_pd(score):
    return 1.0 / (1.0 + 2.0 ** ((score - 600) / 50.0))


def tasa_default_por_tramo(scores, defaults, bin_width=20, min_n=10):
    bins = np.arange(scores.min(), scores.max(), bin_width)
    idx = np.digitize(scores, bins) - 1
    curve, centers = [], []
    for b in range(len(bins) - 1):
        mask_b = idx == b
        if mask_b.sum() >= min_n:
            curve.append(defaults[mask_b].mean() * 100)
            centers.append((bins[b] + bins[b+1]) / 2)
    return centers, curve


def completar_variables_entrada(X_sel, variables_modelo, columnas_entrada, medianas):
    """De las variables del modelo a la entrada completa del pipeline (resto = medianas de train)."""
    X_sel = pd.DataFrame(np.asarray(X_sel, dtype=float).reshape(-1, len(variables_modelo)), columns=variables_modelo)
    D = pd.DataFrame(np.tile(medianas.values, (len(X_sel), 1)), columns=columnas_entrada)
    D[variables_modelo] = X_sel.values
    return D


def crear_predictor_lime(modelo, variables_modelo, columnas_entrada, medianas):
    def predecir_para_lime(X):
        return modelo.predict_proba(completar_variables_entrada(X, variables_modelo, columnas_entrada, medianas))
    return predecir_para_lime


def transformar_espacio_clasificador(modelo, X_full):
    """Pasos previos al clasificador, tal como los aplica predict_proba (el resampler solo actua en fit)."""
    Z = X_full
    for _n, _paso in modelo.steps[:-1]:
        if _paso is None or _paso == 'passthrough' or hasattr(_paso, 'fit_resample'):
            continue
        Z = _paso.transform(Z)
    return np.asarray(Z, dtype=float)


def formato_signo_coma(v, f):
    return format(v, f).replace('.', ',')


def predecir_con_modelo_guardado(payload, X_new):
    """P(default) con el payload guardado: el pipeline completo recibe las variables candidatas (las que
    falten quedan vacias y las imputa el propio pipeline)."""
    info = payload[next(iter(payload.keys()))]
    X = X_new.reindex(columns=info['input_columns']).replace([np.inf, -np.inf], np.nan).astype('float64')
    return info['modelo'].predict_proba(X)[:, 1]
