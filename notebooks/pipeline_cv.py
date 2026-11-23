"""Pipeline con todo el preprocesamiento dentro de cada fold (flujo de Geron, Hands-On ML, cap. 2).

Orden: imputacion -> seleccion (RFECV / IV / Chi2) -> outliers -> transformacion (Raw / YJ / Deciles)
       -> escalado (LR, MLP) -> balanceo (SMOTE / SMOTEENN) -> clasificador.

Todos los pasos se ajustan solo con los datos de entrenamiento de cada fold, porque RandomizedSearchCV
clona y re-ajusta el pipeline completo en cada particion. La seleccion es el unico paso caro (RFECV):
se guarda en un cache en disco, indexado por el contenido de los datos, para no recalcularla en cada
iteracion de la busqueda de hiperparametros.
"""
import os
import time
import pickle
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin, clone
from sklearn.feature_selection import RFECV, chi2
from sklearn.model_selection import GroupKFold, RandomizedSearchCV
from sklearn.preprocessing import PowerTransformer, StandardScaler, KBinsDiscretizer
from sklearn.pipeline import Pipeline
from imblearn.pipeline import Pipeline as ImbPipeline

try:   # solo se usa al entrenar (seleccion por IV); el API carga el modelo sin funciones.py
    from funciones import calc_iv_train
except ImportError:
    calc_iv_train = None


# ---------------------------------------------------------------- cache de la seleccion
class CacheEnDisco:
    def __init__(self, path):
        self.path = path
        if path:
            os.makedirs(path, exist_ok=True)

    def get(self, key):
        if not self.path:
            return None
        f = os.path.join(self.path, key + '.pkl')
        if os.path.exists(f):
            try:
                with open(f, 'rb') as fh:
                    return pickle.load(fh)
            except Exception:
                return None
        return None

    def put(self, key, value):
        if not self.path:
            return
        f = os.path.join(self.path, key + '.pkl')
        tmp = f + f'.{os.getpid()}.tmp'
        with open(tmp, 'wb') as fh:
            pickle.dump(value, fh)
        os.replace(tmp, f)


def a_dataframe(X, cols=None, index=None):
    if isinstance(X, pd.DataFrame):
        return X
    return pd.DataFrame(X, columns=cols, index=index)


# ---------------------------------------------------------------- 1. imputacion
class MedianImputer(BaseEstimator, TransformerMixin):
    """Mediana por columna (ajustada en el fold), con inf -> NaN. Conserva el DataFrame."""

    def fit(self, X, y=None):
        X = a_dataframe(X).replace([np.inf, -np.inf], np.nan)
        self.medians_ = X.median()
        self.columns_ = list(X.columns)
        return self

    def transform(self, X):
        X = a_dataframe(X, self.columns_).replace([np.inf, -np.inf], np.nan)
        return X.fillna(self.medians_).astype('float64')


# ---------------------------------------------------------------- 2. seleccion
class FeatureSelector(BaseEstimator, TransformerMixin):
    """Seleccion supervisada ajustada en el fold.

    method: 'RFECV' (estimator + scale), 'IV' (umbral) o 'Chi2' (alpha sobre deciles).
    grupos: Series con el RUT indexada como X (para el GroupKFold interno de la RFECV).
    """

    def __init__(self, method='RFECV', estimator=None, scale=False, step=5, min_features=5,
                 iv_threshold=0.1, alpha=0.05, grupos=None, cache_dir=None):
        self.method = method
        self.estimator = estimator
        self.scale = scale
        self.step = step
        self.min_features = min_features
        self.iv_threshold = iv_threshold
        self.alpha = alpha
        self.grupos = grupos
        self.cache_dir = cache_dir

    def clave_cache(self, X, y):
        est = repr(sorted(self.estimator.get_params().items())) if self.estimator is not None else ''
        clave = (self.method, est, self.scale, self.step, self.min_features,
                 self.iv_threshold, self.alpha, list(X.columns),
                 X.values, np.asarray(y), list(X.index))
        if self.method == 'Chi2':   # Chi2 depende del discretizador: su version entra en la clave de la cache
            clave = (DecileTransformer.VERSION,) + clave
        return joblib.hash(clave)

    def seleccionar_variables(self, X, y):
        y = np.asarray(y).astype(int)
        cols = list(X.columns)
        if self.method == 'IV':
            yf = y.astype(float)
            out = []
            for c in cols:
                iv, _ = calc_iv_train(X[c].values.astype(float), yf)
                if not np.isnan(iv) and iv >= self.iv_threshold:
                    out.append(c)
            return out
        if self.method == 'Chi2':
            Xd = DecileTransformer().fit(X).transform(X)
            _, p = chi2(Xd.values, y)
            return [c for c, pv in zip(cols, p) if pv < self.alpha]
        if self.method == 'RFECV':
            Xf = X
            if self.scale:
                Xf = pd.DataFrame(StandardScaler().fit_transform(X), columns=cols, index=X.index)
            g = self.grupos.loc[X.index].values
            rf = RFECV(estimator=clone(self.estimator), step=self.step, cv=GroupKFold(n_splits=5),
                       scoring='roc_auc', min_features_to_select=self.min_features, n_jobs=1)
            rf.fit(Xf, y, groups=g)
            return [c for c, s in zip(cols, rf.support_) if s]
        raise ValueError(self.method)

    def fit(self, X, y):
        X = a_dataframe(X)
        cache = CacheEnDisco(self.cache_dir)
        key = self.clave_cache(X, y)
        sel = cache.get(key)
        if sel is None:
            sel = self.seleccionar_variables(X, y)
            cache.put(key, sel)
        if len(sel) == 0:                      # nunca dejar el modelo sin variables
            sel = list(X.columns)
        self.selected_ = sel
        return self

    def transform(self, X):
        return a_dataframe(X)[self.selected_]


# ---------------------------------------------------------------- 3. outliers
class OutlierClipper(BaseEstimator, TransformerMixin):
    """Recorte con limites del fold: 'Raw' (nada), 'Winsor' (p1-p99), 'IQR' (1,5 IQR), 'Z-score' (3 sd)."""

    def __init__(self, method='Raw'):
        self.method = method

    def fit(self, X, y=None):
        X = a_dataframe(X)
        v = X.values.astype('float64')
        if self.method == 'Raw':
            lo = np.full(v.shape[1], -np.inf); hi = np.full(v.shape[1], np.inf)
        elif self.method == 'Winsor':
            lo = np.nanpercentile(v, 1, axis=0); hi = np.nanpercentile(v, 99, axis=0)
        elif self.method == 'IQR':
            q1 = np.nanpercentile(v, 25, axis=0); q3 = np.nanpercentile(v, 75, axis=0)
            lo = q1 - 1.5 * (q3 - q1); hi = q3 + 1.5 * (q3 - q1)
        elif self.method == 'Z-score':
            mu = np.nanmean(v, axis=0); sd = np.nanstd(v, axis=0); sd[sd == 0] = 1
            lo = mu - 3 * sd; hi = mu + 3 * sd
        else:
            raise ValueError(self.method)
        with np.errstate(invalid='ignore'):
            degen = ~(hi > lo)                 # columnas degeneradas (p. ej. indicadoras con IQR = 0)
        self.lo_ = np.where(degen, -np.inf, lo)
        self.hi_ = np.where(degen, np.inf, hi)
        self.columns_ = list(X.columns)
        return self

    def transform(self, X):
        X = a_dataframe(X, self.columns_)
        return pd.DataFrame(np.clip(X.values.astype('float64'), self.lo_, self.hi_),
                            columns=X.columns, index=X.index)


# ---------------------------------------------------------------- 4. transformaciones
class DecileTransformer(BaseEstimator, TransformerMixin):
    """Deciles 0-9 por columna, ajustados en el fold. Solo se discretizan las variables continuas.

    - Continuas: KBinsDiscretizer por cuantiles (10 bins).
    - Binarias (dos valores, como las cualitativas codificadas): pasan como 0/1. Los cuantiles las
      dejaban constantes, y Chi-cuadrado las acepta tal cual.
    - Continuas con un valor que concentra casi todo (p. ej. 99% de ceros), donde los cuantiles caen
      en un solo bin: ese valor es el codigo 0 y el resto se divide por cuantiles en los codigos 1 a 9.
      Si hubiera valores por debajo del valor dominante, se usa el rango medio.
    """
    VERSION = 'solo_continuas_v1'

    def fit(self, X, y=None):
        X = a_dataframe(X)
        self.columns_ = list(X.columns)
        self.reglas_ = {}
        for c in self.columns_:
            x = X[c].values.astype('float64')
            u = np.unique(x)
            if u.size <= 1:
                self.reglas_[c] = ('const',)
                continue
            if u.size == 2:
                self.reglas_[c] = ('bin', u[0], u[1])
                continue
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                kb = KBinsDiscretizer(n_bins=10, encode='ordinal', strategy='quantile').fit(x.reshape(-1, 1))
            if kb.n_bins_[0] >= 2:
                self.reglas_[c] = ('kb', kb)
                continue
            vals, cnt = np.unique(x, return_counts=True)
            m = vals[np.argmax(cnt)]
            resto = x[x != m]
            if (resto < m).any():
                self.reglas_[c] = ('midrank', np.sort(x))
                continue
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                kb2 = KBinsDiscretizer(n_bins=min(9, np.unique(resto).size), encode='ordinal',
                                       strategy='quantile').fit(resto.reshape(-1, 1))
            self.reglas_[c] = ('masa', m, kb2)
        return self

    def transform(self, X):
        X = a_dataframe(X, self.columns_)
        out = {}
        for c in self.columns_:
            r = self.reglas_[c]
            x = X[c].values.astype('float64')
            if r[0] == 'const':
                out[c] = np.zeros(len(x))
            elif r[0] == 'bin':
                out[c] = (x > (r[1] + r[2]) / 2).astype('float64')
            elif r[0] == 'kb':
                out[c] = r[1].transform(x.reshape(-1, 1)).ravel()
            elif r[0] == 'masa':
                m, kb2 = r[1], r[2]
                cod = np.zeros(len(x))
                arriba = x > m
                if arriba.any():
                    cod[arriba] = 1 + kb2.transform(x[arriba].reshape(-1, 1)).ravel()
                out[c] = cod
            else:  # rango medio
                srt = r[1]
                f = (np.searchsorted(srt, x, 'left') + np.searchsorted(srt, x, 'right')) / (2.0 * len(srt))
                out[c] = np.clip(np.floor(10 * f), 0, 9)
        return pd.DataFrame(out, index=X.index)[self.columns_]


class YeoJohnson(BaseEstimator, TransformerMixin):
    """Yeo-Johnson estandarizada, con inf -> 0 y recorte al rango de float32 (igual que el pipeline original)."""

    def fit(self, X, y=None):
        X = a_dataframe(X)
        self.columns_ = list(X.columns)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            self.pt_ = PowerTransformer(method='yeo-johnson', standardize=True).fit(X.values)
        return self

    def transform(self, X):
        X = a_dataframe(X, self.columns_)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            v = self.pt_.transform(X.values)
        v[~np.isfinite(v)] = 0.0
        m = np.finfo(np.float32).max
        v = np.clip(v, -m, m)
        return pd.DataFrame(v, columns=X.columns, index=X.index)


class DFScaler(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        X = a_dataframe(X)
        self.columns_ = list(X.columns)
        self.sc_ = StandardScaler().fit(X.values)
        return self

    def transform(self, X):
        X = a_dataframe(X, self.columns_)
        return pd.DataFrame(self.sc_.transform(X.values), columns=X.columns, index=X.index)


# ---------------------------------------------------------------- pipeline y busqueda
def build_full_pipeline(classifier, selector, outlier, transform, use_scaler, resampler_cls, resampler_kwargs):
    steps = [('imputer', MedianImputer()), ('selector', selector), ('outliers', OutlierClipper(outlier))]
    if transform == 'YJ':
        steps.append(('yj', YeoJohnson()))
    elif transform == 'Deciles':
        steps.append(('deciles', DecileTransformer()))
    if use_scaler:
        steps.append(('scaler', DFScaler()))
    if resampler_cls is not None:
        steps.append(('resampler', resampler_cls(**(resampler_kwargs or {}))))
        steps.append(('classifier', classifier))
        return ImbPipeline(steps)
    steps.append(('classifier', classifier))
    return Pipeline(steps)


def estrategias(outliers, transforms, selectores, resamplings):
    """Las 140 combinaciones del trabajo: Chi2 solo con deciles; deciles nunca con YJ."""
    out = []
    for o in outliers:
        for t in transforms:
            for s in selectores:
                if s.startswith('Chi2') and t != 'Deciles':
                    continue
                for r in resamplings:
                    out.append((o, t, s, r))
    return out


def metricas_oof(y, p, per_fold, folds):
    """Metricas sobre probabilidades fuera de muestra. El umbral es el promedio de los umbrales de
    maxima separacion KS de cada fold (como en la tesis): no usa el test ni el conjunto completo."""
    from sklearn.metrics import roc_auc_score, roc_curve, precision_score, recall_score, f1_score, brier_score_loss
    y = np.asarray(y).astype(int)
    thr = []
    for (tr, va), pv in zip(folds, per_fold):
        f_, t_, th_ = roc_curve(y[va], pv)
        thr.append(float(th_[np.argmax(t_ - f_)]))
    u = float(np.mean(thr))
    pred = (p >= u).astype(int)
    f_, t_, _ = roc_curve(y, p)
    return {'AUC_OOF': float(roc_auc_score(y, p)), 'KS': float(np.max(t_ - f_)), 'Umbral': u,
            'Precision': float(precision_score(y, pred, zero_division=0)),
            'Recall': float(recall_score(y, pred)), 'F1': float(f1_score(y, pred)),
            'Alertas_%': float(pred.mean()), 'Brier': float(brier_score_loss(y, p)),
            'Prob_media': float(p.mean())}


def evaluar_busqueda(search, cv_splits):
    cvr = search.cv_results_
    k = int(np.nanargmax(cvr['mean_test_score']))
    out = {'CV_AUC': float(cvr['mean_test_score'][k]), 'CV_std': float(cvr['std_test_score'][k]),
           'Train_AUC_CV': float(cvr['mean_train_score'][k]), 'Best_Params': cvr['params'][k],
           'n_configs': int(np.sum(~np.isnan(cvr['mean_test_score'])))}
    out['Overfit_CV'] = out['Train_AUC_CV'] - out['CV_AUC']
    for j in range(cv_splits):
        out[f'fold{j}'] = float(cvr[f'split{j}_test_score'][k])
    return out


def run_full_grid(model_name, classifier, param_grid, X, y, grupos, selectores, configs_resampling,
                  use_scaler, n_iter=30, cv_splits=5, n_jobs=-1, random_state=42,
                  outliers=('Raw', 'Winsor', 'IQR', 'Z-score'), transforms=('Raw', 'YJ', 'Deciles'),
                  log=print, out_csv=None, folds=None):
    """Busqueda sobre estrategias x hiperparametros con TODO el preprocesamiento dentro del pipeline.

    Por estrategia: RandomizedSearchCV (n_iter) y, con los mejores hiperparametros, probabilidades fuera
    de muestra en los mismos folds para calcular el punto de operacion y la calibracion. El sobreajuste
    se mide sin el test: AUC de entrenamiento de cada fold menos AUC de validacion (Overfit_CV).
    Devuelve (DataFrame de resultados, dict de la mejor por CV, folds, dict estrategia -> OOF).
    """
    rs_map = {n: (c, kw) for n, c, kw in configs_resampling}
    combos = estrategias(outliers, transforms, list(selectores), list(rs_map))
    if folds is None:
        folds = list(GroupKFold(n_splits=cv_splits).split(X, y, groups=grupos))
    rows, best, oofs = [], None, {}
    t0 = time.time()
    for i, (o, t, s, r) in enumerate(combos, 1):
        rs_cls, rs_kw = rs_map[r]
        pipe = build_full_pipeline(clone(classifier), clone(selectores[s]), o, t, use_scaler, rs_cls, rs_kw)
        search = RandomizedSearchCV(pipe, param_grid, n_iter=n_iter, scoring='roc_auc', cv=folds,
                                    n_jobs=n_jobs, random_state=random_state, refit=False,
                                    error_score=np.nan, return_train_score=True)
        strategy = f'{o} + {t} + {s} + {r}'
        try:
            search.fit(X, y)
            ev = evaluar_busqueda(search, cv_splits)
            p, pf = oof_predict(clone(pipe).set_params(**ev['Best_Params']), X, y, folds)
        except Exception as e:                       # una estrategia que falla no corta la busqueda
            log(f'[{i}/{len(combos)}] {strategy}  FALLA: {e}')
            continue
        row = {'Modelo': model_name, 'Etapa': 'Exploracion', 'Strategy': strategy, 'outlier': o,
               'transform': t, 'features': s, 'resampling': r, **ev, **metricas_oof(y, p, pf, folds)}
        rows.append(row)
        oofs[strategy] = (p, pf)
        if best is None or row['CV_AUC'] > best['CV_AUC']:
            best = row
        el = time.time() - t0
        log(f'[{i}/{len(combos)}] {strategy}  CV {row["CV_AUC"]:.4f} ± {row["CV_std"]:.4f}  '
            f'overfit {row["Overfit_CV"]:.3f}  recall {row["Recall"]:.3f}  '
            f'(mejor {best["CV_AUC"]:.4f}; {el/60:.0f} min, ETA {el/i*(len(combos)-i)/60:.0f} min)')
        if out_csv:
            pd.DataFrame(rows).to_csv(out_csv, index=False)
    return pd.DataFrame(rows), best, folds, oofs


def es_numero(v):
    return isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool) and v is not None


def grilla_local(best_params, param_grid):
    """Grilla alrededor de los mejores hiperparametros: para cada numerico, el valor ganador, sus vecinos en
    la grilla original y los puntos intermedios (geometricos si la escala es multiplicativa). Los
    categoricos (p. ej. 'sqrt', tuplas de capas) se fijan en el valor ganador."""
    out = {}
    for k, vals in param_grid.items():
        b = best_params[k]
        nums = sorted(v for v in vals if es_numero(v))
        if not es_numero(b) or len(nums) < 2:
            out[k] = [b]
            continue
        es_int = all(isinstance(v, (int, np.integer)) for v in nums)
        i = nums.index(b) if b in nums else int(np.argmin([abs(v - b) for v in nums]))
        cand = {b}
        for j in (i - 1, i + 1):
            if 0 <= j < len(nums):
                nb = nums[j]
                cand.add(nb)
                lo, hi = min(b, nb), max(b, nb)
                mid = np.sqrt(lo * hi) if lo > 0 and hi / lo > 2.5 else (lo + hi) / 2
                mid = int(round(mid)) if es_int else float(f'{mid:.3g}')
                cand.add(mid)
        # si el ganador quedo en un borde de la grilla original, se prueba tambien un valor algo mas alla
        if b == nums[0] and b > 0:
            ext = b * 0.75
            ext = max(1, int(round(ext))) if es_int else float(f'{ext:.3g}')
            if ext != b:
                cand.add(ext)
        if b == nums[-1] and not any(v is None for v in vals):
            ext = b * 1.25
            ext = int(round(ext)) if es_int else float(f'{ext:.3g}')
            if ext != b and not (isinstance(b, float) and b <= 1 and ext > 1 and k.endswith(('max_samples', 'max_features', 'subsample', 'colsample_bytree'))):
                cand.add(ext)
        if any(v is None for v in vals) and b is not None and i == len(nums) - 1:
            cand.add(None)                           # p. ej. max_depth=None en el arbol
        out[k] = sorted(cand, key=lambda v: (v is None, v if v is not None else 0))
    return out


def ajuste_fino(row, model_name, classifier, param_grid, X, y, selectores, configs_resampling, use_scaler,
                folds, n_jobs=-1, max_configs=150, random_state=42):
    """GridSearchCV local (o aleatoria, si la grilla local supera max_configs) con la estrategia fija."""
    from sklearn.model_selection import GridSearchCV, ParameterGrid
    params = row['Best_Params'] if isinstance(row['Best_Params'], dict) else __import__('ast').literal_eval(row['Best_Params'])
    local = grilla_local(params, param_grid)
    n = len(ParameterGrid(local))
    rs_map = {n_: (c, kw) for n_, c, kw in configs_resampling}
    rs_cls, rs_kw = rs_map[row['resampling']]
    pipe = build_full_pipeline(clone(classifier), clone(selectores[row['features']]), row['outlier'],
                               row['transform'], use_scaler, rs_cls, rs_kw)
    if n <= max_configs:
        search = GridSearchCV(pipe, local, scoring='roc_auc', cv=folds, n_jobs=n_jobs, refit=False,
                              error_score=np.nan, return_train_score=True)
    else:
        search = RandomizedSearchCV(pipe, local, n_iter=max_configs, scoring='roc_auc', cv=folds,
                                    n_jobs=n_jobs, random_state=random_state, refit=False,
                                    error_score=np.nan, return_train_score=True)
    search.fit(X, y)
    ev = evaluar_busqueda(search, len(folds))
    p, pf = oof_predict(clone(pipe).set_params(**ev['Best_Params']), X, y, folds)
    out = {'Modelo': model_name, 'Etapa': 'Ajuste fino', 'Strategy': row['Strategy'], 'outlier': row['outlier'],
           'transform': row['transform'], 'features': row['features'], 'resampling': row['resampling'],
           **ev, **metricas_oof(y, p, pf, folds), 'Grilla_local': local, 'n_grilla_local': n,
           'Mejora_vs_exploracion': ev['CV_AUC'] - row['CV_AUC'],
           'Error_estandar': row['CV_std'] / np.sqrt(len(folds))}
    return out, (p, pf)


def pipeline_from_row(row, classifier, selectores, configs_resampling, use_scaler):
    rs_map = {n: (c, kw) for n, c, kw in configs_resampling}
    rs_cls, rs_kw = rs_map[row['resampling']]
    pipe = build_full_pipeline(clone(classifier), clone(selectores[row['features']]), row['outlier'],
                               row['transform'], use_scaler, rs_cls, rs_kw)
    params = row['Best_Params']
    if isinstance(params, str):
        import ast
        params = ast.literal_eval(params)
    pipe.set_params(**params)
    return pipe


def oof_predict(pipe, X, y, folds):
    """Probabilidades fuera de muestra con los mismos folds de la busqueda (pipeline completo por fold)."""
    p = np.full(len(y), np.nan)
    per_fold = []
    for tr, va in folds:
        m = clone(pipe).fit(X.iloc[tr], y.iloc[tr])
        pv = m.predict_proba(X.iloc[va])[:, 1]
        p[va] = pv
        per_fold.append(pv)
    return p, per_fold
