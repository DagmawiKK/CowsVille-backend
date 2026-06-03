from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (BreedTypeViewSet, CowViewSet,
                    DataCollectorSubmitAnimalView,
                    DataCollectorSubmitFarmView, DataCollectorViewSet,
                    DoctorViewSet, FarmerMedicalReportViewSet, FarmViewSet,
                    FeedingFrequencyViewSet, FloorTypeViewSet,
                    GeneralHealthStatusViewSet, GynecologicalStatusViewSet,
                    HousingTypeViewSet, InseminationRecordViewSet,
                    InseminatorViewSet, MastitisStatusViewSet,
                    MedicalAssessmentViewSet, MessageViewSet,
                    ReproductionViewSet, UdderHealthStatusViewSet,
                    WaterSourceViewSet)

router = DefaultRouter()

# Main model endpoints
router.register(r"farms", FarmViewSet)
router.register(r"cows", CowViewSet)
router.register(r"reproduction", ReproductionViewSet)
router.register(r"inseminators", InseminatorViewSet)
router.register(r"messages", MessageViewSet)
router.register(r"doctors", DoctorViewSet)
# Choice model endpoints
router.register(r"breedtypes", BreedTypeViewSet)
router.register(r"housingtypes", HousingTypeViewSet)
router.register(r"floortypes", FloorTypeViewSet)
router.register(r"feedingfrequencies", FeedingFrequencyViewSet)
router.register(r"watersources", WaterSourceViewSet)
router.register(r"gynecologicalstatuses", GynecologicalStatusViewSet)
router.register(r"udderhealthstatuses", UdderHealthStatusViewSet)
router.register(r"mastitisstatuses", MastitisStatusViewSet)
router.register(r"generalhealthstatuses", GeneralHealthStatusViewSet)

router.register(r"farmer-medical-reports", FarmerMedicalReportViewSet)
router.register(r"medical-assessments", MedicalAssessmentViewSet)
router.register(r"insemination-records", InseminationRecordViewSet)
router.register(r"data-collectors", DataCollectorViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("submit-farm/", DataCollectorSubmitFarmView.as_view(), name="submit-farm"),
    path("submit-animal/", DataCollectorSubmitAnimalView.as_view(), name="submit-animal"),
]
