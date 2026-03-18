from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from accounts.models import Skill


class Session(models.Model):
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='sessions')
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_sessions')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=200)
    date_time = models.DateTimeField()
    duration = models.DurationField()
    capacity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.skill_id and self.host_id and self.skill.owner != self.host:
            raise ValidationError("You can only create sessions for your own skills.")

    def __str__(self):
        return f"{self.title} ({self.skill.name})"


class SessionMembership(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='session_memberships')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['session', 'user'], name='unique_session_membership')
        ]

    def __str__(self):
        return f"{self.user.username} in {self.session.title}"
