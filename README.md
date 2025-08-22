# Mortgage Calculator

A Django-based web application for calculating mortgage payments with support for grace periods.

## Features

- **Mortgage Calculation**: Calculate monthly payments, total loan amount, and overpayment for mortgages
- **Grace Period Support**: Option to include a grace period with different interest rates
- **Payment Schedule**: Detailed amortization table showing each payment's breakdown
- **Excel Export**: Save calculation results and payment schedule to Excel format
- **Input Validation**: Comprehensive error handling for user inputs
- **Responsive Design**: Clean, user-friendly interface

## Technology Stack

- **Backend**: Django 4.2.7
- **Frontend**: HTML, CSS, JavaScript
- **Data Export**: OpenPyXL for Excel generation
- **Date Handling**: python-dateutil

## Installation

1. Clone or download the project files
2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Apply database migrations:
   ```bash
   python manage.py migrate
   ```

5. Create a superuser (optional, for admin access):
   ```bash
   python manage.py createsuperuser
   ```

6. Run the development server:
   ```bash
   python manage.py runserver
   ```

7. Open your browser and navigate to `http://127.0.0.1:8000/`

## Usage

1. Enter the required mortgage parameters:
   - Property cost (in rubles)
   - Down payment percentage
   - Initial payment date (DD.MM.YYYY format)
   - Mortgage term in years
   - Annual interest rate

2. If applicable, select "Yes" for grace period and provide:
   - Grace period term in years
   - Grace period interest rate

3. Click "Calculate" to see results

4. Optionally, click "Save to Excel" to export the results

## Input Parameters

- Property Cost (rubles)
- Down Payment (%)
- Initial Payment Date (DD.MM.YYYY)
- Mortgage Term (years)
- Annual Interest Rate (%)
- Grace Period (yes/no)
  - If yes: Grace Period Term (years) and Grace Period Interest Rate (%)

## Output Parameters

- Number of grace period payments
- Last payment date of grace period
- Monthly payment during grace period (rubles)
- Loan amount after grace period (rubles)
- Number of main period payments
- Mortgage end date
- Monthly payment during main period (rubles)
- Total loan amount (rubles)
- Total overpayment (rubles)
- Detailed payment schedule

## Project Structure

```
mortgage_calculator/
├── manage.py
├── mortgage/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── calculator/
    ├── __init__.py
    ├── admin.py
    ├── apps.py
    ├── forms.py
    ├── models.py
    ├── views.py
    ├── mortgage_calculator.py
    └── templates/
        └── calculator/
            └── index.html
```

## Key Components

- **MortgageCalculator Class**: Implements the business logic for mortgage calculations
- **MortgageForm**: Handles input validation and data cleaning
- **MortgageCalculation Model**: Stores calculation results in the database
- **Excel Export**: Generates detailed reports in Excel format

## Requirements

- Python 3.8+
- Django 4.2.7
- OpenPyXL 3.1.2
- python-dateutil 2.8.2

## License

This project is open source and available under the MIT License.

## Support

For issues or questions regarding this application, please check the Django documentation or create an issue in the project repository.