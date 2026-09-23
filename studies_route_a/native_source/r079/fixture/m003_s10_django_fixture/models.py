from django.db import models

class Document(models.Model):
    id = models.AutoField(primary_key=True)
    myfile = models.FileField(upload_to='unused', unique=True)

    class Meta:
        app_label = 'm003_s10_django_fixture'
        db_table = 's10_r79_document'
