from setuptools import setup

setup(name = 'gee_fwi',
    author = 'Josef Matondang',
    author_email = 'admin@josefmtd.com',
    version = '1.0.3',
    description = 'Google Earth Engine Fire Weather Index Calculator',
    classifiers = [
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.8',
    ],
    keywords = 'fire weather index',
    url = 'https://github.com/josefmtd/gee-fwi',
    license = 'MIT',
    packages = ['gee_fwi'],
    install_requires = [
        'earthengine-api',
        'eemont',
    ],
    include_package_data = True,
    zip_safe = False)
