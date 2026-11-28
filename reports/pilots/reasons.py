"""Why a load was rejected, in words: the ETL log, the batch journal API, readyz and Reports UI show this, not only a code."""

NAMES = {'tracker': 'Task Tracker', 'planning': 'Planning System', 'reference': 'Reference Manager', 'qa': 'QA System'}
# The owner's role for the Reports service account; Infra grants it (070, section 5).
ROLES = {'tracker': 'reports-service', 'planning': 'reports.export (S-06)', 'reference': 'reference-reader', 'qa': 'qa-reports-reader'}
CONTRACT = {'INVALID_JSON', 'MISSING_ID', 'DUPLICATE_ID', 'INVALID_PAGE_METADATA', 'INVALID_PAGE', 'PAGE_MISMATCH',
            'UNSTABLE_PAGES', 'COUNT_MISMATCH', 'INCOMPLETE_PAGE', 'EMPTY_PAGE', 'INVALID_ITEM', 'PAGE_LIMIT',
            'INVALID_HR_PAGE', 'INVALID_HR_ID', 'REPEATED_CURSOR', 'INVALID_PROFILE_PAGE', 'INVALID_PROFILE',
            'INVALID_PROFILE_ID', 'REPEATED_PROFILE_CURSOR', 'PROFILE_PAGE_LIMIT', 'INVALID_BATCH_ID', 'FOREIGN_BATCH',
            'TRACKER_CONTRACT_VIOLATION', 'UNSUPPORTED_HR_RESOURCE', 'RESPONSE_TOO_LARGE'}
KEEP = 'Данные этого источника в отчётах остаются прежними и помечаются устаревшими.'


def explain(code, source=None):
    """A sentence for people about a rejection code of the ETL."""
    if not code: return None
    name = NAMES.get(source, 'Источник')
    if code == 'SOURCE_HTTP_401':
        return f'{name} не принял вход Reports (401): токен служебного входа недействителен или выдан другим Keycloak. {KEEP}'
    if code == 'SOURCE_HTTP_403':
        role = ROLES.get(source, 'на чтение данных для Reports')
        return f'{name} отказал в доступе (403): служебному входу Reports не выдана роль {role}. Роль выдаёт Infra по заявке. {KEEP}'
    if code.startswith('SOURCE_HTTP_5') or code in {'SOURCE_UNAVAILABLE', 'DEPENDENCY_UNAVAILABLE'}:
        return f'{name} недоступен; следующая загрузка повторит попытку. {KEEP}'
    if code.startswith('SOURCE_HTTP_'):
        return f'{name} ответил ошибкой {code.removeprefix("SOURCE_HTTP_")}. {KEEP}'
    if code in CONTRACT:
        return f'{name} отдал данные не по своему контракту ({code}); загрузка отклонена целиком. {KEEP}'
    if code == 'SOURCE_LOAD_IN_PROGRESS':
        return f'Загрузка {name} уже идёт; эту выполнит следующий такт.'
    if code == 'OUT_OF_ORDER_BATCH':
        return f'Партия {name} старше уже загруженной и не применяется, чтобы не откатить данные назад.'
    if code == 'LOAD_FAILED':
        return f'Ошибка записи в хранилище при загрузке {name}; изменения отменены. {KEEP}'
    return f'Загрузка {name} отклонена ({code}). {KEEP}'
