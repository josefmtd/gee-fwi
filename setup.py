from setuptools import setup

def readme():
    with open('README.md') as f:
        return f.read()

setup(name = 'gee_fwi',
    version = '1.0',
    description = 'Google Earth Engine Fire Weather Index Calculator',
    long_description = readme(),
    classifiers = [
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.8',
        'Topic :: Climate',
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
