# -*- coding: utf-8 -*-
import json
from translator.errors import ErrorEnum
from django.http import HttpResponse


def get_json(request, field_name):
    try:
        json_data = json.loads(request.body)
    except Exception:
        return None
    return json_data.get(field_name)


def error_response(error: ErrorEnum):
    result = {'error_code': error, 'error_message': error.name.replace('_', ' ').capitalize()}

    return HttpResponse(json.dumps(result, ensure_ascii=False), status=422,
                        content_type='application/json; charset=utf-8')


def success(data=None):
    if not data:
        data = {}
    return HttpResponse(json.dumps(data, ensure_ascii=False),
                        content_type='application/json; charset=utf-8')
