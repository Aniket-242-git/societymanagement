from django.db.models import Count
from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from API.apps.core.permissions import IsAdminOrCommittee
from API.apps.core.exceptions import first_error_message
from API.apps.core.responses import api_error, api_success
from API.apps.issues.models import Issue, IssueComment, IssueResolution, IssueVote
from API.apps.issues.serializers import (
    IssueCommentSerializer, IssueCreateSerializer, IssueDetailSerializer,
    IssueListSerializer, IssueResolveSerializer, IssueStatusSerializer,
)


class IssueViewSet(viewsets.ModelViewSet):
    """Residents raise/vote/comment; admin/committee triage & resolve."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = (
            Issue.objects.filter(is_active=True)
            .select_related("flat", "created_by", "resolution", "resolution__resolved_by")
            .prefetch_related("images", "comments__user", "votes")
            .annotate(vote_count=Count("votes", distinct=True), comment_count=Count("comments", distinct=True))
        )
        user = self.request.user
        # residents only see society-wide issues; scoping by ?mine=true filters their own
        mine = self.request.query_params.get("mine")
        if mine == "true":
            qs = qs.filter(flat__owner=user)
        status_f = self.request.query_params.get("status")
        if status_f:
            qs = qs.filter(status=status_f)
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)
        return qs.order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "create":
            return IssueCreateSerializer
        if self.action == "retrieve":
            return IssueDetailSerializer
        return IssueListSerializer

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        ser = self.get_serializer
        if page is not None:
            return self.get_paginated_response(ser(page, many=True).data)
        return api_success(data=ser(self.get_queryset(), many=True).data)

    def retrieve(self, request, pk=None, *args, **kwargs):
        try:
            obj = self.get_queryset().get(pk=pk)
        except Issue.DoesNotExist:
            return api_error("Issue not found", status=404)
        return api_success(data=IssueDetailSerializer(obj, context={"request": request}).data)

    def create(self, request, *args, **kwargs):
        ser = IssueCreateSerializer(data=request.data, context={"request": request})
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        ser.save()
        return api_success("Issue raised successfully", data=IssueDetailSerializer(ser.instance, context={"request": request}).data, status=201)

    def destroy(self, request, pk=None, *args, **kwargs):
        try:
            obj = Issue.objects.get(pk=pk, is_active=True)
        except Issue.DoesNotExist:
            return api_error("Issue not found", status=404)
        obj.is_active = False
        obj.save(update_fields=["is_active"])
        return api_success("Issue deleted successfully")

    # ------------------------------------------------------------- voting
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def vote(self, request, pk=None):
        """Toggle upvote (one vote per user per issue)."""
        try:
            issue = Issue.objects.get(pk=pk, is_active=True)
        except Issue.DoesNotExist:
            return api_error("Issue not found", status=404)
        existing = IssueVote.objects.filter(issue=issue, user=request.user).first()
        if existing:
            existing.delete()
            return api_success("Vote removed", data={"voted": False, "vote_count": issue.votes.count()})
        IssueVote.objects.create(issue=issue, user=request.user)
        return api_success("Issue upvoted", data={"voted": True, "vote_count": issue.votes.count()})

    # ------------------------------------------------------------- comments
    @action(detail=True, methods=["post", "get"], permission_classes=[IsAuthenticated], url_path="comments")
    def comments(self, request, pk=None):
        try:
            issue = Issue.objects.get(pk=pk, is_active=True)
        except Issue.DoesNotExist:
            return api_error("Issue not found", status=404)
        if request.method == "GET":
            return api_success(data=IssueCommentSerializer(
                issue.comments.select_related("user").all(), many=True).data)
        ser = IssueCommentSerializer(data=request.data, context={"request": request})
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        ser.save(user=request.user, issue=issue)
        return api_success("Comment added successfully", data=ser.data, status=201)

    # ------------------------------------------------------------- admin workflow
    @action(detail=True, methods=["patch"], permission_classes=[IsAdminOrCommittee])
    def status(self, request, pk=None):
        try:
            issue = Issue.objects.get(pk=pk, is_active=True)
        except Issue.DoesNotExist:
            return api_error("Issue not found", status=404)
        ser = IssueStatusSerializer(data=request.data)
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        issue.status = ser.validated_data["status"]
        issue.save(update_fields=["status", "updated_at"])
        return api_success("Issue status updated successfully",
                           data=IssueDetailSerializer(issue, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminOrCommittee])
    def resolve(self, request, pk=None):
        """Add resolution remark (+ optional image) and mark issue resolved."""
        try:
            issue = Issue.objects.get(pk=pk, is_active=True)
        except Issue.DoesNotExist:
            return api_error("Issue not found", status=404)
        ser = IssueResolveSerializer(data=request.data)
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        with transaction.atomic():
            res, _ = IssueResolution.objects.update_or_create(
                issue=issue,
                defaults={"remark": ser.validated_data["remark"],
                          "image": ser.validated_data.get("image"),
                          "resolved_by": request.user},
            )
            issue.status = "resolved"
            issue.save(update_fields=["status", "updated_at"])
        return api_success("Issue resolved successfully",
                           data=IssueDetailSerializer(issue, context={"request": request}).data)
