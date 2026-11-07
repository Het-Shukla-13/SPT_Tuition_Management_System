from rest_framework.routers import SimpleRouter

from apps.academics.views import (
    AcademicYearViewSet,
    BoardViewSet,
    ChapterViewSet,
    SchoolViewSet,
    StandardViewSet,
    SubjectViewSet,
)

router = SimpleRouter()
router.register("boards", BoardViewSet, basename="board")
router.register("standards", StandardViewSet, basename="standard")
router.register("subjects", SubjectViewSet, basename="subject")
router.register("chapters", ChapterViewSet, basename="chapter")
router.register("schools", SchoolViewSet, basename="school")
router.register("academic-years", AcademicYearViewSet, basename="academic-year")

urlpatterns = router.urls
