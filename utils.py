import redis
import json
import time
import os
from functools import wraps
from flask import current_app

# Redis connection for caching
try:
    redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
    redis_available = True
except:
    redis_available = False


def cache_result(timeout=300):
    """Decorator for caching function results"""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not redis_available:
                return f(*args, **kwargs)

            key = f"{f.__name__}_{str(args)}_{str(kwargs)}"

            try:
                cached = redis_client.get(key)
                if cached:
                    return json.loads(cached)
            except:
                pass

            result = f(*args, **kwargs)

            try:
                redis_client.setex(key, timeout, json.dumps(result, default=str))
            except:
                pass

            return result

        return decorated_function

    return decorator


def invalidate_cache_pattern(pattern):
    """Invalidate cache keys matching pattern"""
    if not redis_available:
        return

    try:
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
    except:
        pass


def get_db_connection_info():
    """Get database connection info for monitoring"""
    try:
        from models import db
        engine = db.engine
        pool = engine.pool

        return {
            'pool_size': pool.size(),
            'checked_in': pool.checkedin(),
            'checked_out': pool.checkedout(),
            'overflow': pool.overflow(),
            'invalid': pool.invalid()
        }
    except:
        return None


def monitor_performance():
    """Monitor application performance"""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            result = f(*args, **kwargs)
            end_time = time.time()

            duration = end_time - start_time
            if duration > 1.0:  # Log slow requests
                print(f"Slow request: {f.__name__} took {duration:.2f}s")

            return result

        return decorated_function

    return decorator