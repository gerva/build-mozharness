def per_locale_summary(func):
    """calls add_success/failure based on locale"""
    def wrapper(self, *args, **kwargs):
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
    return wrapper

def time_for_step(func):
    """prints out how long it took to run func"""
    import time
    def now():
        return int(round(time.time()))

    def wrapper(self, *args, **kwargs):
        name = func.__name__
        start_time = now()
        locale = kwargs.get('locale', None)
        try:
            result = func(self, *args, **kwargs)
        except:
            delta = str(now() - start_time)
            message = '%s failed in %s seconds (locale=%s)' %(name, delta, locale)
            self.info(message)
            raise
        delta = (now() - start_time)
        message = '%s completed in %s seconds (locale=%s)' %(name, delta, locale)
        self.info(message)
        return result
    return wrapper

