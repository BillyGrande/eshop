from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, FloatField, TextAreaField, IntegerField, SelectField
from wtforms.validators import DataRequired, NumberRange, Optional

class ProductForm(FlaskForm):
    name = StringField('Product Name', validators=[DataRequired()])
    price = FloatField('Price', validators=[DataRequired(), NumberRange(min=0.01)])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional()])
    brand = StringField('Brand', validators=[Optional()])
    tags = StringField('Tags (comma-separated)', validators=[Optional()])
    stock_quantity = IntegerField('Stock Quantity', validators=[DataRequired(), NumberRange(min=0)])
    discount_percentage = FloatField('Discount Percentage', validators=[Optional(), NumberRange(min=0, max=100)])
    image = FileField('Product Image', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')])