from typing import Any

from . import consulentia_engine as engine
from .auth import save_report_record


def _fallback_bundle(profile: str, error: str) -> dict[str, Any]:
    return {
        'profile': profile,
        'raw': {
            'profile_label': profile.capitalize(),
            'timestamp': 'dati temporaneamente non disponibili',
            'equity_funds': [],
            'bond_funds': [],
            'commodity_funds': [],
            'abs_return_funds': [],
        },
        'markets': [
            {'name': 'S&P500', 'last': 'n.d.', 'trend': 'n.d.'},
            {'name': 'Nasdaq', 'last': 'n.d.', 'trend': 'n.d.'},
            {'name': 'Oro', 'last': 'n.d.', 'trend': 'n.d.'},
            {'name': 'Petrolio', 'last': 'n.d.', 'trend': 'n.d.'},
        ],
        'fractals': [],
        'macro': [],
        'allocation_base': {},
        'allocation_tactical': {},
        'allocation_comment': 'I dati live non sono disponibili in questo momento. Riprova tra poco.',
        'outlook': 'Dashboard temporaneamente in modalità di sicurezza.',
        'traffic_summary': 'Semafori: dati non disponibili',
        'fractal_summary': 'Analisi tecnica temporaneamente non disponibile',
        'intermarket_notes': [f'Errore temporaneo: {error}'],
        'news': ['Nessuna news disponibile al momento.'],
        'error': error,
    }


def get_dashboard_bundle(profile: str) -> dict[str, Any]:
    try:
        data = engine.build_dashboard_data(profile)
        return {
            'profile': profile,
            'raw': data,
            'markets': data.get('markets', []),
            'fractals': data.get('fractal_analyses', []),
            'macro': data.get('macro_table', []),
            'allocation_base': data.get('base_allocation', {}),
            'allocation_tactical': data.get('final_allocation', {}),
            'allocation_comment': data.get('strategy', ''),
            'outlook': data.get('outlook', ''),
            'traffic_summary': data.get('traffic_summary', ''),
            'fractal_summary': data.get('fractal_summary', ''),
            'intermarket_notes': data.get('intermarket_notes', []),
            'news': data.get('news', []),
            'error': None,
        }
    except Exception as exc:
        return _fallback_bundle(profile, str(exc))


def generate_user_report(user_id: int, profile: str) -> dict[str, str]:
    data = engine.build_dashboard_data(profile)
    text = engine.build_text_report(data)
    txt_path = engine.save_text_report(profile, text)
    engine.save_snapshot(profile, data, txt_path)
    docx_path = engine.save_docx_report(txt_path, text)
    pdf_path = engine.save_pdf_report(txt_path, data)
    report_id = save_report_record(
        user_id=user_id,
        profile=profile,
        txt_path=str(txt_path),
        pdf_path=str(pdf_path),
        docx_path=str(docx_path),
    )
    return {
        'report_id': str(report_id),
        'txt_path': str(txt_path),
        'pdf_path': str(pdf_path),
        'docx_path': str(docx_path),
    }