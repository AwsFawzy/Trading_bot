# هذا الملف يحوّل هذا المجلد إلى حزمة بايثون
# This file converts this folder into a Python package

# إضافة مرشح لقوالب Jinja2 للتعامل مع القيم غير المعرفة في عملية التقريب
def init_jinja_filters(app):
    """
    إضافة مرشحات مخصصة لنظام قوالب Jinja2
    """
    @app.template_filter('safe_round')
    def safe_round_filter(value, precision=2):
        """
        تقريب آمن يتعامل مع القيم غير المعرفة أو غير القابلة للتحويل
        """
        if value is None or value == "" or value == "undefined" or value == "null":
            return 0.0
        try:
            return round(float(value), precision)
        except (ValueError, TypeError):
            return 0.0
