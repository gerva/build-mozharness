def decorator__(func):
    def _decorator(self, *args, **kwargs):
        name = func.__name__
        locale = kwargs.get('locale', None)
        message = 'success: %s, locale = %s' %(name, locale)
        if func(self, *args, **kwargs) == 0:
            pass
        else:
            message = 'failure: %s, locale = %s' %(name, locale)
        self.info(message)
    return _decorator
