"""Lee un formulario de estados contables del BROU (FORM_BCE 2018) y muestra las variables del modelo.

El lector vive en el API (credit-scoring-api/app/form_bce.py), que es el que usa el dashboard para importar el
.xlsx; este script lo usa tal cual para revisar un formulario desde la terminal.

Uso: python ejemplos/leer_formulario.py <formulario .xlsx>
"""
import importlib.util
import sys
from pathlib import Path

_RUTA = Path(__file__).resolve().parent.parent / 'credit-scoring-api' / 'app' / 'form_bce.py'
_spec = importlib.util.spec_from_file_location('form_bce', _RUTA)
form_bce = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(form_bce)
leer = form_bce.leer

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Uso: python ejemplos/leer_formulario.py <formulario .xlsx>')
    for k, x in leer(sys.argv[1]).items():
        print(f'{k:45s} {x:,.0f}' if isinstance(x, float) else f'{k:45s} {x}')
