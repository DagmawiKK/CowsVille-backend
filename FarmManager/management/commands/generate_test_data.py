"""
Management command to generate test data for pagination testing.

Usage:
    python manage.py generate_test_data [--farms=N] [--cows-per-farm=N]
        [--assessments=N] [--submissions=N] [--reports=N] [--delete-existing]

Generates:
    - N farms with unique farm_ids and realistic owner names
    - N cows per farm with sequential cow_ids
    - N medical assessments spread across doctors/cows
    - N data collector submissions with varied form types
    - N farmer medical reports spread across cows
"""

import random
from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from FarmManager.models import (
    BreedType, HousingType, FloorType, FeedingFrequency,
    WaterSource, GynecologicalStatus, UdderHealthStatus,
    MastitisStatus, GeneralHealthStatus,
    Farm, Cow, Doctor, MedicalAssessment,
    FarmerMedicalReport, DataCollectorSubmission, DataCollector,
    User,
)

# --- Helpers ---

FIRST_NAMES = [
    "Abebe", "Almaz", "Belay", "Biruk", "Chaltu", "Desta", "Ephrem", "Fikir",
    "Genet", "Girma", "Hanna", "Henok", "Hiwot", "Jemal", "Kebede", "Lemlem",
    "Mahlet", "Mekdes", "Meron", "Meseret", "Mulu", "Nigus", "Selam", "Sisay",
    "Tadesse", "Tariku", "Tesfaye", "Tigist", "Wondimu", "Worku", "Yonas", "Zeru",
]

LAST_NAMES = [
    "Abera", "Alemu", "Assefa", "Bekele", "Dagne", "Defar", "Demissie",
    "Desalegn", "Eshetu", "Fikadu", "Getachew", "Hailu", "Kassahun",
    "Legesse", "Mamo", "Mekonnen", "Melaku", "Shiferaw", "Tadesse",
    "Tefera", "Wondimu", "Worku", "Yilma", "Zeleke",
]

CHOICE_FIELDS = {
    "udder_health": ["4qt_normal", "3qt_normal", "2qt_normal", "1qt_normal"],
    "mastitis": ["negative", "clinical_mastitis", "cmt_plus", "cmt_plus_plus", "cmt_plus_plus_plus"],
    "general_health": ["normal", "sick"],
    "reproductive_health": ["normal", "abortion", "still_birth", "dystocia", "rfm", "endometritis", "metritis", "prolapse", "other"],
    "metabolic_disease": ["normal", "hypocalcema", "vit_a_deficiency", "mg_deficiency", "ketosis", "acidosis", "other"],
    "sickness_type": ["infectious", "non_infectious"],
}


def random_phone():
    return f"+2519{random.randint(10,99)}{random.randint(100000,999999)}"


def random_date(start_year=2018, end_year=2025):
    start = date(start_year, 1, 1).toordinal()
    end = date(end_year, 12, 31).toordinal()
    return date.fromordinal(random.randint(start, end))
def random_datetime(start_year=2023, end_year=2025):
    d = random_date(start_year, end_year)
    t = datetime.min.time().replace(hour=random.randint(0, 23), minute=random.randint(0, 59))
    return datetime.combine(d, t)


def random_choice(options):
    return random.choice(options)


def random_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def random_farm_id(index):
    """Generate FARM-001 style IDs."""
    return f"FARM-{index:04d}"


def random_cow_id(farm_index, cow_index):
    return f"ET-{farm_index:04d}-{cow_index:04d}"


class Command(BaseCommand):
    help = "Generate test data for pagination testing"

    def add_arguments(self, parser):
        parser.add_argument("--farms", type=int, default=25, help="Number of farms (default: 25)")
        parser.add_argument("--cows-per-farm", type=int, default=10, help="Cows per farm (default: 10)")
        parser.add_argument("--assessments", type=int, default=100, help="Medical assessments (default: 100)")
        parser.add_argument("--submissions", type=int, default=50, help="Data collector submissions (default: 50)")
        parser.add_argument("--reports", type=int, default=50, help="Farmer medical reports (default: 50)")
        parser.add_argument("--delete-existing", action="store_true", help="Delete existing data first")

    def handle(self, *args, **options):
        num_farms = options["farms"]
        cows_per_farm = options["cows_per_farm"]
        num_assessments = options["assessments"]
        num_submissions = options["submissions"]
        num_reports = options["reports"]
        delete_existing = options["delete_existing"]

        if delete_existing:
            self.stdout.write("Deleting existing data...")
            MedicalAssessment.objects.all().delete()
            FarmerMedicalReport.objects.all().delete()
            DataCollectorSubmission.objects.all().delete()
            Cow.objects.all().delete()
            Farm.objects.all().delete()

        # Ensure choice models have data
        self._ensure_choice_models()

        # Ensure we have doctors
        doctors = list(Doctor.objects.all())
        if not doctors:
            doctors = self._create_doctors(3)

        # Ensure we have a data collector
        dc = DataCollector.objects.first()
        if not dc:
            dc = self._create_data_collector()

        self.stdout.write("Generating farms...")
        farms = self._create_farms(num_farms)

        self.stdout.write("Generating cows...")
        all_cows = []
        for i, farm in enumerate(farms[:num_farms]):
            cows = self._create_cows(farm, cows_per_farm, i + 1)
            all_cows.extend(cows)

        self.stdout.write("Generating medical assessments...")
        self._create_assessments(all_cows, doctors, num_assessments)

        self.stdout.write("Generating farmer medical reports...")
        self._create_reports(all_cows, doctors, num_reports)

        self.stdout.write("Generating data collector submissions...")
        self._create_submissions(dc, num_submissions)

        # Summary
        self.stdout.write(self.style.SUCCESS(
            f"\nDone! "
            f"Farms: {Farm.objects.count()}, "
            f"Cows: {Cow.objects.count()}, "
            f"MedicalAssessments: {MedicalAssessment.objects.count()}, "
            f"FarmerMedicalReports: {FarmerMedicalReport.objects.count()}, "
            f"DataCollectorSubmissions: {DataCollectorSubmission.objects.count()}"
        ))

    def _ensure_choice_models(self):
        """Ensure choice tables have seed data."""
        choices = {
            BreedType: ["Holstein Friesian", "Jersey", "Boran", "Sanga", "Crossbreed"],
            HousingType: ["free_stall", "tie_stall", "open_lot", "compost_barn"],
            FloorType: ["concrete", "stone", "soil", "mat_bedding"],
            FeedingFrequency: ["once", "twice", "thrice"],
            WaterSource: ["tap_water", "wells"],
            GynecologicalStatus: ["estrus", "ai", "pregnant", "abortion", "fresh", "birth"],
            UdderHealthStatus: ["4qt_normal", "3qt_normal", "2qt_normal", "1qt_normal"],
            MastitisStatus: ["negative", "clinical_mastitis", "cmt_plus", "cmt_plus_plus", "cmt_plus_plus_plus"],
            GeneralHealthStatus: ["normal", "sick"],
        }
        for model, names in choices.items():
            existing = set(model.objects.values_list("name", flat=True))
            for name in names:
                if name not in existing:
                    model.objects.create(name=name)

    def _create_doctors(self, count):
        doctors = []
        for i in range(count):
            name = random_name()
            doctor = Doctor.objects.create(
                name=name,
                phone_number=random_phone(),
                address=f"{random.choice(['Addis Ababa', 'Bahir Dar', 'Mekelle', 'Dire Dawa', 'Hawassa'])}",
                license_number=f"LIC-{random.randint(10000,99999)}",
                specialization=random_choice(["Large Animal", "Reproduction", "General Vet"]),
            )
            doctors.append(doctor)
            self.stdout.write(f"  Created doctor: {doctor.name}")
        return doctors

    def _create_data_collector(self):
        dc = DataCollector.objects.create(
            name=random_name(),
            phone_number=random_phone(),
            address="Addis Ababa",
        )
        self.stdout.write(f"  Created data collector: {dc.name}")
        return dc

    @transaction.atomic
    def _create_farms(self, count):
        housing = list(HousingType.objects.all())
        floors = list(FloorType.objects.all())
        feeding = list(FeedingFrequency.objects.all())
        water = list(WaterSource.objects.all())

        farms = []
        existing_ids = set(Farm.objects.values_list("farm_id", flat=True))

        i = 1
        while len(farms) < count:
            fid = random_farm_id(i)
            if fid in existing_ids:
                i += 1
                continue
            farm = Farm.objects.create(
                farm_id=fid,
                owner_name=random_name(),
                address=f"{random.randint(100,999)} {random.choice(['Main St', 'Church Ave', 'Market Rd', 'Lake Dr', 'Highland Way'])}, {random.choice(['Addis Ababa', 'Bahir Dar', 'Mekelle', 'Dire Dawa', 'Hawassa'])}",
                telephone_number=random_phone(),
                location_gps=f"{random.uniform(3.0, 15.0):.4f}, {random.uniform(33.0, 48.0):.4f}",
                cluster_number=random_choice([f"CL-{x}" for x in range(1, 8)] + [None]),
                fertility_camp_no=random.randint(0, 10),
                total_number_of_cows=random.randint(5, 50),
                number_of_calves=random.randint(1, 20),
                number_of_milking_cows=random.randint(2, 30),
                total_daily_milk=random.randint(20, 500),
                type_of_housing=random.choice(housing),
                type_of_floor=random.choice(floors),
                main_feed=random_choice(["Hay", "Silage", "Concentrate mix", "Pasture", "Crop residue"]),
                rate_of_cow_feeding=random.choice(feeding),
                source_of_water=random.choice(water),
                rate_of_water_giving=random.choice(feeding),
                farm_hygiene_score=random.randint(1, 4),
            )
            farms.append(farm)
            i += 1

        self.stdout.write(f"  Created {len(farms)} farms")
        return farms

    @transaction.atomic
    def _create_cows(self, farm, count, farm_index):
        breeds = list(BreedType.objects.all())
        gyno = list(GynecologicalStatus.objects.all())
        existing_ids = set(Cow.objects.filter(farm=farm).values_list("cow_id", flat=True))

        cows = []
        c = 1
        while len(cows) < count:
            cid = random_cow_id(farm_index, c)
            if cid in existing_ids:
                c += 1
                continue
            dob = random_date(2018, 2023)
            cow = Cow.objects.create(
                farm=farm,
                cow_id=cid,
                breed=random.choice(breeds),
                date_of_birth=dob,
                sex=random.choice(["F", "F", "F", "M"]),  # mostly females
                parity=random.randint(0, 6),
                body_weight=random.randint(250, 650),
                bcs=random.choice([1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]),
                gynecological_status=random.choice(gyno),
                lactation_number=random.randint(0, 5),
                days_in_milk=random.randint(0, 305),
                average_daily_milk=random.uniform(5.0, 35.0),
                cow_inseminated_before=random.random() > 0.3,
                last_date_insemination=random_date(2023, 2025),
                number_of_inseminations=random.randint(0, 5),
                id_or_breed_bull_used=random_choice(["", "AI Bull-1", "AI Bull-2", "Natural"]),
                last_calving_date=random_date(2023, 2025),
            )
            cows.append(cow)
            c += 1

        self.stdout.write(f"  Created {len(cows)} cows for farm {farm.farm_id}")
        return cows

    @transaction.atomic
    def _create_assessments(self, cows, doctors, count):
        health_statuses = list(GeneralHealthStatus.objects.all())
        udder_statuses = list(UdderHealthStatus.objects.all())
        mastitis_statuses = list(MastitisStatus.objects.all())

        existing = MedicalAssessment.objects.count()
        to_create = count - existing
        if to_create <= 0:
            self.stdout.write(f"  Already have {existing} assessments, skipping")
            return

        batch = []
        for i in range(to_create):
            cow = random.choice(cows)
            doctor = random.choice(doctors)
            is_sick = random.random() > 0.5
            has_diag_tx = random.random() > 0.4

            assessment = MedicalAssessment(
                farm=cow.farm,
                cow=cow,
                assessed_by=doctor,
                assessment_date=random_datetime(2024, 2026),
                is_cow_sick=is_sick,
                sickness_type=random.choice(["infectious", "non_infectious"]) if is_sick else None,
                general_health=random.choice(health_statuses),
                udder_health=random.choice(udder_statuses),
                mastitis=mastitis_statuses[0] if random.random() > 0.3 else random.choice(mastitis_statuses),
                has_lameness=random.random() > 0.7,
                body_condition_score=random.randint(1, 5),
                reproductive_health=random.choice(["normal", "abortion", "still_birth", "dystocia", "rfm", "endometritis", "metritis", "prolapse", "other"]),
                metabolic_disease=random.choice(["normal", "hypocalcema", "vit_a_deficiency", "mg_deficiency", "ketosis", "acidosis", "other"]),
                is_cow_vaccinated=random.random() > 0.3,
                vaccination_date=random_date(2024, 2025) if random.random() > 0.3 else None,
                vaccination_type=random.choice(["BVD", "IBR", "Blackleg", "Anthrax", ""]) if random.random() > 0.3 else "",
                has_deworming=random.random() > 0.4,
                deworming_date=random_date(2024, 2025) if random.random() > 0.4 else None,
                deworming_type=random.choice(["Albendazole", "Ivermectin", "Fenbendazole", ""]) if random.random() > 0.4 else "",
                diagnosis=random.choice(["Bovine Respiratory Disease", "Mastitis", "Metritis", "Foot rot", "Pneumonia", ""]) if has_diag_tx else "",
                treatment=random.choice(["Antibiotics", "Anti-inflammatory", "Fluid therapy", "Surgery", ""]) if has_diag_tx else "",
                prescription=random.choice(["Penicillin 10ml IM x5d", "Oxytetracycline 20ml IM x3d", "Flunixin 5ml IV x3d", ""]) if has_diag_tx else "",
                next_assessment_date=random_date(2025, 2026) if random.random() > 0.6 else None,
                notes=random.choice(["", "Cow is recovering well", "Needs follow-up next week", "Owner instructed on care"]) if random.random() > 0.4 else "",
            )
            batch.append(assessment)

        MedicalAssessment.objects.bulk_create(batch, batch_size=500)
        self.stdout.write(f"  Created {to_create} medical assessments")

    @transaction.atomic
    def _create_reports(self, cows, doctors, count):
        existing = FarmerMedicalReport.objects.count()
        to_create = count - existing
        if to_create <= 0:
            self.stdout.write(f"  Already have {existing} reports, skipping")
            return

        batch = []
        for _ in range(to_create):
            cow = random.choice(cows)
            report = FarmerMedicalReport(
                farm=cow.farm,
                cow=cow,
                sickness_description=random.choice([
                    "Cow has reduced appetite and fever",
                    "Limping on hind leg, possible injury",
                    "Milk production dropped significantly",
                    "Coughing and nasal discharge",
                    "Diarrhea for 3 days",
                    "Swollen udder, possible mastitis",
                ]),
                reported_date=random_datetime(2024, 2026),
                is_reviewed=random.random() > 0.4,
                reviewed_by=random.choice(doctors) if random.random() > 0.4 else None,
                review_date=random_datetime(2024, 2026) if random.random() > 0.4 else None,
            )
            batch.append(report)

        FarmerMedicalReport.objects.bulk_create(batch, batch_size=500)
        self.stdout.write(f"  Created {to_create} farmer medical reports")

    @transaction.atomic
    def _create_submissions(self, dc, count):
        existing = DataCollectorSubmission.objects.count()
        to_create = count - existing
        if to_create <= 0:
            self.stdout.write(f"  Already have {existing} submissions, skipping")
            return

        batch = []
        for _ in range(to_create):
            batch.append(DataCollectorSubmission(
                form_type=random.choice(["farm", "animal"]),
                submitted_data={"sample": "data", "generated": True},
                status=random.choice(["pending", "approved", "rejected"]),
                submitted_at=random_datetime(2024, 2026),
                submitted_by=dc,
                notes=random.choice(["", "Generated test data", "OK", "Needs review"]) if random.random() > 0.5 else "",
            ))

        DataCollectorSubmission.objects.bulk_create(batch, batch_size=500)
        self.stdout.write(f"  Created {to_create} data collector submissions")
