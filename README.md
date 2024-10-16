# visa_rescheduler
The visa_rescheduler is a bot for US VISA (usvisa-info.com) appointment rescheduling. This bot can help you reschedule your appointment to your desired time period.

## Prerequisites
- Having a US VISA appointment scheduled already.

## Attention
- A list of supported embassies is presented in the 'embassy.py' file.
- To add a new embassy (using English), you should find the embassy's "facility id." To do this, using google chrome, on the booking page of your account, right-click on the location section, then click "inspect." Then the right-hand window will be opened, highlighting the "select" item. You can find the "facility id" here and add this facility id in the 'embassy.py' file. There might be several facility ids for several different embassies. They can be added too. Please use the picture below as an illustration of the process.
![Alt Finding Facility id](./_img.png)

## Initial Setup
- Install Google Chrome [for install goto: https://www.google.com/chrome/]
- Install Python v3 [for install goto: https://www.python.org/downloads/]
- Start a virtual environment called, preferably one called `myenv` by running `python3 -m venv myenv`
- Install the required python packages my running `pip install -r requirements.txt` OR use the steps below
- Install the required python packages: Just run the below commands:
```
pip install requests==2.27.1
pip install selenium==4.2.0
pip install webdriver-manager==3.7.0
pip install pygame>=2.4.0
```

OR use `pip install -r requirements.txt`

## How to use
- Initial setup!
- Edit the information [config.example.ini file]. Then remove the ".example" from file name.
- Edit the `EMBASSIES_TO_CHECK` variable in `visa.py` to be a list of the embassies you want to check. Use `embassy.py` to see the codes for the embassies you want to check
- Run visa.py file, using `python3 visa.py`

## TODO's to consider
- Make timing optimum. (There are lots of unanswered questions. How is the banning algorithm? How can we avoid it? etc.)
- Adding a GUI (Based on PyQt)
- Multi-account support (switching between accounts in Resting times)
