# EShop

A Flask-based e-commerce web application with product recommendations.

## Features

- Responsive homepage with modern design
- Product recommendation section
- Category browsing
- Mobile-friendly interface

## Project Structure

```
eshop/
├── src/
│   ├── app.py                 # Main Flask application
│   ├── eshop/                 # Python package for business logic
│   │   └── __init__.py        
│   ├── static/                # Static assets
│   │   ├── style.css          # CSS styles
│   │   └── images/            # Product and category images
│   ├── templates/             # HTML templates
│   │   └── index.html         # Homepage template
│   └── steps.txt              # Development log
├── .flaskenv                  # Flask environment variables
├── pyproject.toml             # Project metadata and dependencies
├── requirements.lock          # Locked dependencies
└── requirements-dev.lock      # Development dependencies
```

## Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install -e .
   ```
3. Run the development server:
   ```
   flask run
   ```

## Usage

Visit http://localhost:5000 in your web browser to view the homepage.

## Development

The application is built using Flask. See `steps.txt` for more information about the development process and decisions.