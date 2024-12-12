from setuptools import setup, find_packages

setup(
    name='bib-tidy',
    version='1.0.0',
    packages=find_packages(),
    install_requires=[
        'bibtexparser',
    ],
    entry_points={
        'console_scripts': [
            'bib-tidy=bib_tidy.main:main',
        ],
    },
    author='ffxdd',
    author_email='your.email@example.com',
    description='A tool for cleaning and formatting BibTeX files',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/yourusername/bibtex-tidy',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)