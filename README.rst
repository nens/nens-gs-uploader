nens-gs-uploader
==========================================

Introduction

De nens-gs-uploader kan gebruikt worden voor het snel uploaden van grote hoeveelheden aan shapefiles.
Dit script met gebruik van python 3.


Installation
------------

De nens-gs-uploader kan op dit moment alleen geïnstalleerd worden door de bestanden te downloaden vanaf deze github pagina.
In de toekomst kan dit met een pip install::

  $ pip install nens-gs-uploader
   
Quick start
-----------

* Wanneer geen pip install nens_gs_uploader is gebruikt moet je het volgende command runnen::
  $ pip install --user -r nens_gs_uploader/data/requirements.txt
  Deze installeert de benodigde libraries in het script.
    
* Maak een kopie van "instellingen_voorbeeld.ini" voor de specifieke shapes die je wilt uploaden.
* Vul localsecret.py in met de gegevens van de server en inloggegevens van de geoservers. 
  Vraag aan Chris als of je deze kan krijgen als je ze nog niet hebt.
* Run het script met het volgende command::
  $ python nens_gs_uploader.py pad_naar_inifile/inifile.ini
 

Development installation of this project itself
-----------------------------------------------

We're installed with `pipenv <https://docs.pipenv.org/>`_, a handy wrapper
around pip and virtualenv. Install that first with ``pip install
pipenv``. Then run::

  $ PIPENV_VENV_IN_PROJECT=1 pipenv --three
  $ pipenv install --dev

There will be a script you can run like this::

  $ pipenv run run-nens-gs-uploader

It runs the `main()` function in `nens-gs-uploader/scripts.py`,
adjust that if necessary. The script is configured in `setup.py` (see
`entry_points`).

In order to get nicely formatted python files without having to spend manual
work on it, run the following command periodically::

  $ pipenv run black nens_gs_uploader

Run the tests regularly. This also checks with pyflakes, black and it reports
coverage. Pure luxury::

  $ pipenv run pytest

The tests are also run automatically `on travis-ci
<https://travis-ci.com/nens/nens-gs-uploader>`_, you'll see it
in the pull requests. There's also `coverage reporting
<https://coveralls.io/github/nens/nens-gs-uploader>`_ on
coveralls.io (once it has been set up).

If you need a new dependency (like `requests`), add it in `setup.py` in
`install_requires`. Afterwards, run install again to actuall install your
dependency::

  $ pipenv install --dev


