def per_locale_summary(func):
    """calls add_success/failure based on locale"""
    def _decorator(self, *args, **kwargs):
        name = func.__name__
        locale = kwargs.get('locale', None)
        result = func(self, *args, **kwargs)
        if result == 0:
            # success!
            # there's no add_success method...
            # message = 'success: %s, locale = %s' %(name, locale)
            # self.add_success(locale, message)
            pass
        else:
            message = 'failure: %s, locale = %s' %(name, locale)
            self.add_failure(locale, message)
        return result
    return _decorator
