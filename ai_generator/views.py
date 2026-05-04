import json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt

from .services import rewrite_for_threads
from .trending import get_trending_from_db, get_trending_live


@csrf_exempt
@require_POST
def rewrite_view(request):
    """POST /ai/rewrite/ — переписать текст в стиле Threads."""
    try:
        data = json.loads(request.body)
        raw_text = data.get("text", "").strip()
        language = data.get("language", "ru")

        if not raw_text:
            return JsonResponse({"error": "Текст не может быть пустым"}, status=400)
        if len(raw_text) > 2000:
            return JsonResponse({"error": "Текст слишком длинный (макс. 2000 символов)"}, status=400)

        result = rewrite_for_threads(raw_text, language)
        return JsonResponse({"result": result})

    except RuntimeError as e:
        return JsonResponse({"error": str(e)}, status=503)
    except Exception as e:
        return JsonResponse({"error": f"Внутренняя ошибка: {e}"}, status=500)


@csrf_exempt
def trending_view(request):
    """
    GET /ai/trending/           — тренды из базы
    GET /ai/trending/?live=1    — тренды из живого Threads
    GET /ai/trending/?lang=ru   — фильтр по языку (ru/kz/en/all)
    """
    live = request.GET.get("live") == "1"
    lang_filter = request.GET.get("lang", "all")

    try:
        if live:
            topics = get_trending_live(top_n=40)
        else:
            topics = get_trending_from_db(hours=72, top_n=40)

        # Фильтр по языку
        if lang_filter != "all":
            topics = [t for t in topics if t.get("lang") == lang_filter]

        return JsonResponse({"topics": topics[:20], "live": live, "lang": lang_filter})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
