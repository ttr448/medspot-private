from django.db import models

class Medicine(models.Model):
    name = models.CharField(max_length=255)
    active_ingredient = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=255, blank=True)  # e.g., analgesic, antibiotic
    strength = models.CharField(max_length=100, blank=True, default="")  # e.g., 500 mg

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name