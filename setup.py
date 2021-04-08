#!/usr/bin/env python
from setuptools import setup

setup(name='django-qshop',
      version='1.2.3',
      description='E-commerce for django. Requires django-sitemenu. Beta version.',
      long_description='E-commerce for django. Requires django-sitemenu. Beta version.',
      author='Vital Belikov',
      author_email='vital@qwe.lv',
      packages=['qshop', 'qshop.templatetags', 'qshop.cart', 'qshop.management',
                'qshop.management.commands', 'qshop.payment_vendors', 'qshop.payment_vendors.banktransfer',
                'qshop.payment_vendors.paypal', 'qshop.payment_vendors.webmoney'],
      url='https://github.com/Brick85/django-qshop',
      include_package_data=True,
      zip_safe=False,
      requires=['django(>=2.0)', 'django_sitemenu', 'easy_thumbnails'],
      classifiers=['Development Status :: 5 - Beta',
                   'Environment :: Web Environment',
                   'Framework :: Django',
                   'Intended Audience :: Developers',
                   'License :: OSI Approved :: BSD License',
                   'Natural Language :: English',
                   'Operating System :: Unix',
                   'Programming Language :: Python :: 3.6',
                   'Topic :: Utilities'],
      license='New BSD')
