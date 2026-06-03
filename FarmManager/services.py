"""
Business logic services for the Farm Manager application
"""

import logging
from typing import Any, Dict, Optional, Tuple

from django.db import transaction

from AlertSystem.sendMesage import send_alert

from .constants import DefaultHealthStatus, MessageTemplates, MessageTypes
from .models import (DataCollectorSubmission, Doctor, GeneralHealthStatus,
                     MastitisStatus, Message, UdderHealthStatus)

logger = logging.getLogger(__name__)


class MessagingService:
    """Service class to handle all messaging and notifications"""

    @staticmethod
    def send_notification_with_message_record(
        phone_number: str,
        message_text: str,
        message_type: str,
        farm,
        cow=None,
        log_prefix: str = "",
    ) -> Tuple[bool, str]:
        """
        Send a notification and create a message record

        Returns:
            Tuple[bool, str]: (success, error_message)
        """
        try:
            response = send_alert(phone_number, message_text)
            is_sent = response.get("status") == "success"

            if is_sent:
                logger.info(f"{log_prefix} Alert sent successfully")
            else:
                logger.warning(f"{log_prefix} Failed to send alert")

            # Create message record regardless of send status
            Message.objects.create(
                farm=farm,
                cow=cow,
                message_text=message_text,
                message_type=message_type,
                is_sent=is_sent,
            )

            return is_sent, ""

        except Exception as e:
            error_msg = f"Error sending notification: {str(e)}"
            logger.error(f"{log_prefix} {error_msg}")
            return False, error_msg

    @staticmethod
    def send_heat_sign_notifications(cow, heat_signs: str) -> Dict[str, bool]:
        """
        Send heat sign notifications to both inseminator and farmer

        Returns:
            Dict with 'inseminator_sent' and 'farmer_sent' keys
        """
        results = {"inseminator_sent": False, "farmer_sent": False}

        # Prepare messages
        inseminator_message = MessageTemplates.insemination_alert(
            cow.farm.farm_id,
            cow.farm.owner_name,
            cow.farm.address,
            cow.farm.telephone_number,
            cow.cow_id,
            heat_signs,
        )

        farmer_message = MessageTemplates.farmer_heat_notification(
            cow.cow_id, cow.farm.inseminator.name
        )

        # Send to inseminator
        if cow.farm.inseminator:
            inseminator_sent, _ = (
                MessagingService.send_notification_with_message_record(
                    cow.farm.inseminator.phone_number,
                    inseminator_message,
                    MessageTypes.INSEMINATION_ALERT,
                    cow.farm,
                    cow,
                    f"Inseminator notification for cow {cow.cow_id}:",
                )
            )
            results["inseminator_sent"] = inseminator_sent

        # Send to farmer
        farmer_sent, _ = MessagingService.send_notification_with_message_record(
            cow.farm.telephone_number,
            farmer_message,
            MessageTypes.INSEMINATION_ALERT,
            cow.farm,
            cow,
            f"Farmer notification for cow {cow.cow_id}:",
        )
        results["farmer_sent"] = farmer_sent

        return results

    @staticmethod
    def send_staff_change_notifications(
        farm, staff_type: str, old_staff, new_staff, message_type: str
    ) -> Dict[str, bool]:
        """
        Send notifications for staff changes

        Returns:
            Dict with notification results
        """
        results = {}

        # Notify old staff if exists
        if old_staff:
            old_message = MessageTemplates.staff_unassignment_notice(
                farm.farm_id, farm.owner_name
            )
            old_staff_sent, _ = MessagingService.send_notification_with_message_record(
                old_staff.phone_number,
                old_message,
                message_type,
                farm,
                None,
                f"Old {staff_type} notification:",
            )
            results["old_staff_sent"] = old_staff_sent

        # Notify new staff
        new_message = MessageTemplates.staff_assignment_notice(
            staff_type,
            farm.farm_id,
            farm.owner_name,
            farm.address,
            farm.telephone_number,
        )
        new_staff_sent, _ = MessagingService.send_notification_with_message_record(
            new_staff.phone_number,
            new_message,
            message_type,
            farm,
            None,
            f"New {staff_type} notification:",
        )
        results["new_staff_sent"] = new_staff_sent

        # Notify farmer about doctor change
        if staff_type == "doctor":
            farmer_message = MessageTemplates.doctor_change_farmer_notice(
                new_staff.name, new_staff.phone_number
            )
            farmer_sent, _ = MessagingService.send_notification_with_message_record(
                farm.telephone_number,
                farmer_message,
                message_type,
                farm,
                None,
                "Farmer doctor change notification:",
            )
            results["farmer_sent"] = farmer_sent

        return results


class HealthService:
    """Service class to handle health-related operations"""

    @staticmethod
    def get_default_health_statuses() -> (
        Tuple[Optional[Any], Optional[Any], Optional[Any]]
    ):
        """
        Get default health status objects

        Returns:
            Tuple of (general_health, udder_health, mastitis) objects
        """
        try:
            general_health = GeneralHealthStatus.objects.get(
                name=DefaultHealthStatus.GENERAL_HEALTH_NORMAL
            )
            udder_health = UdderHealthStatus.objects.get(
                name=DefaultHealthStatus.UDDER_HEALTH_NORMAL
            )
            mastitis = MastitisStatus.objects.get(
                name=DefaultHealthStatus.MASTITIS_CLINICAL
            )
            return general_health, udder_health, mastitis
        except Exception as e:
            logger.error(f"Could not find default health status: {str(e)}")
            # Fallback to first available
            general_health = GeneralHealthStatus.objects.first()
            udder_health = UdderHealthStatus.objects.first()
            mastitis = MastitisStatus.objects.first()
            return general_health, udder_health, mastitis

    @staticmethod
    def get_doctor_for_assessment(farm) -> Optional[Doctor]:
        """
        Get a doctor for medical assessment - prefer farm's doctor, fallback to active doctor

        Returns:
            Doctor instance or None
        """
        assessed_by = farm.doctor
        if not assessed_by:
            # Try to get the first available active doctor
            assessed_by = Doctor.objects.filter(is_active=True).first()
            if not assessed_by:
                # If no active doctors, get any doctor
                assessed_by = Doctor.objects.first()

            if assessed_by:
                logger.info(
                    f"No doctor assigned to farm, using fallback doctor: {assessed_by.name}"
                )
            else:
                logger.warning("No doctors available in the system")

        return assessed_by


class ValidationService:
    """Service class for common validation operations"""

    @staticmethod
    def convert_yes_no_to_boolean(value, default: bool = False) -> bool:
        """
        Convert 'yes'/'no' string to boolean

        Args:
            value: The value to convert (can be bool, str, or None)
            default: Default value if conversion fails

        Returns:
            Boolean value
        """
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            normalized = value.lower().strip()
            if normalized in ["yes", "true", "1", "y", "yes_sick"]:
                return True
            elif normalized in ["no", "false", "0", "n", "no_sick"]:
                return False
            else:
                return default
        else:
            return default

    @staticmethod
    def safe_int_conversion(value, default: int = 0) -> int:
        """
        Safely convert value to integer

        Args:
            value: Value to convert
            default: Default value if conversion fails

        Returns:
            Integer value
        """
        try:
            return int(float(value)) if value is not None else default
        except (ValueError, TypeError):
            return default

    @staticmethod
    def format_ethiopian_phone_number(value):
        """
        Helper method to format Ethiopian phone numbers by adding +251 prefix

        Args:
            value: Phone number string to format

        Returns:
            Formatted phone number string
        """
        if not value:
            return value

        # Remove any spaces, dashes, or other formatting
        cleaned_number = "".join(filter(str.isdigit, value.replace("+", "")))

        # If number already starts with +251, return as is
        if value.startswith("+251"):
            return value

        # If number starts with 251, add + prefix
        if cleaned_number.startswith("251"):
            return f"+{cleaned_number}"

        # If number starts with 0 (Ethiopian local format), replace with +251
        if cleaned_number.startswith("0") and len(cleaned_number) == 10:
            return f"+251{cleaned_number[1:]}"

        # If number is 9 digits (Ethiopian mobile without 0), add +251
        if len(cleaned_number) == 9 and cleaned_number[0] in ["9"]:
            return f"+251{cleaned_number}"

        # If none of the above, return original value (will be caught by model validation)
        return value

    @staticmethod
    def map_hygiene_score(value):
        """
        Map hygiene score text to number

        Args:
            value: Hygiene score value (string or number)

        Returns:
            Integer hygiene score (1-4)
        """
        if not value:
            return 2  # Default value

        hygiene_mapping = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "1": 1,
            "2": 2,
            "3": 3,
            "4": 4,
        }
        return hygiene_mapping.get(str(value).lower(), 2)  # Default to 2


class LoggingMixin:
    """Mixin to provide consistent logging patterns"""

    def get_logger(self):
        """Get logger instance for the class"""
        return logging.getLogger(
            self.__class__.__module__ + "." + self.__class__.__name__
        )

    def log_request_received(self, operation: str, data=None):
        """Log incoming request"""
        logger = self.get_logger()
        if data:
            logger.info(f"Received {operation} request with data: {data}")
        else:
            logger.info(f"Received {operation} request")

    def log_operation_success(self, operation: str, identifier: str = ""):
        """Log successful operation"""
        logger = self.get_logger()
        if identifier:
            logger.info(f"Successfully {operation} {identifier}")
        else:
            logger.info(f"Successfully {operation}")

    def log_operation_error(
        self, operation: str, error: Exception, identifier: str = ""
    ):
        """Log operation error"""
        logger = self.get_logger()
        if identifier:
            logger.error(f"Error {operation} {identifier}: {str(error)}", exc_info=True)
        else:
            logger.error(f"Error {operation}: {str(error)}", exc_info=True)

    def log_validation_error(self, operation: str, errors):
        """Log validation errors"""
        logger = self.get_logger()
        try:
            logger.warning(f"Invalid {operation} data: {errors}")
        except (ValueError, TypeError) as e:
            # If errors can't be converted to string, log raw error
            logger.error(f"Error logging validation errors for {operation}: {str(e)}")
            logger.warning(f"Invalid {operation} data (could not serialize errors)")


class ResponseService:
    """Service class for standardized API responses"""

    @staticmethod
    def success_response(message: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create a standardized success response

        Args:
            message: Success message
            data: Additional data to include

        Returns:
            Response dictionary
        """
        response = {"message": message}
        if data:
            response.update(data)
        return response

    @staticmethod
    def error_response(
        message: str, status_code: int = 500
    ) -> Tuple[Dict[str, str], int]:
        """
        Create a standardized error response

        Args:
            message: Error message
            status_code: HTTP status code

        Returns:
            Tuple of (response_dict, status_code)
        """
        return {"error": message}, status_code


class ODKValidationService:
    """Service class for strict server-side validation of ODK form submissions.

    Replicates ODK form constraints including conditional required fields,
    value ranges, and enum lookups to ensure data integrity before storage.
    """

    # --- Farm Data Collection Form Enums ---
    FARM_HOUSING_TYPES = {"free_stall", "tie_stall", "traditional"}
    FARM_FLOOR_TYPES = {"concrete", "stone", "soil", "mat"}
    FARM_FEED_TYPES = {
        "hay", "straw", "green", "wheat_bran", "oil_cake",
        "spent_grain", "byproduct", "molasses",
    }
    FARM_FEEDING_RATES = {"once_day", "twice_day", "thrice_day"}
    FARM_WATER_SOURCES = {"tap_water", "wells"}
    FARM_WATER_RATES = {"once_day", "twice_day", "thrice_day"}
    FARM_HYGIENE_SCORES = {"one", "two", "three", "four"}

    # --- Animal Data Collection Form Enums ---
    ANIMAL_BREEDS = {"hf", "zebu", "hf_zebu", "other"}
    ANIMAL_BCS_VALUES = {"1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5"}
    ANIMAL_GYN_STATUSES = {"estrus", "ai", "pregnant", "abortion", "fresh", "birth"}
    ANIMAL_LACTATION_NUMBERS = {"1.5", "2", "2.5", "3", "3.5", "4", "4.5"}
    ANIMAL_UDDER_HEALTH = {"4qt", "3qt", "2qt", "1qt"}
    ANIMAL_MASTITIS = {"negative", "clinical_mastitis", "cmt1", "cmt2", "cmt3"}
    ANIMAL_GENERAL_HEALTH = {"normal", "sick"}
    ANIMAL_REPRODUCTIVE_HEALTH = {
        "normal", "abortion", "still_birth", "dystocia", "rfm",
        "endometritis", "metritis", "prolapse", "other",
    }
    ANIMAL_METABOLIC_DISEASE = {
        "normal", "hypocalcema", "vit_a_deficiency", "mg_deficiency",
        "ketosis", "acidosis", "other",
    }
    ANIMAL_HEAT_SIGNS = {
        "bellowing", "restlessness", "off_feed", "vaginal_discharge",
        "mounting_other", "standing_for_mount", "head_butting", "chin_resting",
    }
    YES_NO = {"yes", "no"}

    @staticmethod
    def validate_farm_submission(data: Dict[str, Any]) -> Dict[str, str]:
        """Validate farm data collection submission against all ODK constraints.

        Args:
            data: Dictionary of submitted form fields.

        Returns:
            Dictionary of field_name -> error_message. Empty dict = valid.
        """
        errors = {}

        # --- Required string fields ---
        required_strings = ["owner_name", "farm_id", "address"]
        for field in required_strings:
            value = data.get(field)
            if not value or not str(value).strip():
                errors[field] = f"{field} is required."

        # --- Phone number ---
        tel_no = data.get("tel_no")
        if tel_no is None or tel_no == "":
            errors["tel_no"] = "tel_no is required."
        else:
            try:
                tel_str = str(tel_no)
                cleaned = "".join(filter(str.isdigit, tel_str.replace("+", "")))
                if not (9 <= len(cleaned) <= 15):
                    errors["tel_no"] = "tel_no must be a valid phone number (9-15 digits)."
            except (ValueError, TypeError):
                errors["tel_no"] = "tel_no must be a valid number."

        # --- GPS (optional, format check if provided) ---
        gps = data.get("location_gps")
        if gps:
            parts = str(gps).strip().split()
            if len(parts) < 2:
                errors["location_gps"] = "location_gps must be in 'lat lng [alt accuracy]' format."
            else:
                try:
                    float(parts[0])
                    float(parts[1])
                except ValueError:
                    errors["location_gps"] = "location_gps latitude and longitude must be numeric."

        # --- Integer fields with constraints ---
        int_fields_positive = {
            "fcc_no": "fcc_no must be greater than 0.",
            "herd_size": "herd_size must be greater than 0.",
        }
        for field, msg in int_fields_positive.items():
            value = data.get(field)
            if value is None or value == "":
                errors[field] = f"{field} is required."
            else:
                try:
                    ival = int(value)
                    if ival <= 0:
                        errors[field] = msg
                except (ValueError, TypeError):
                    errors[field] = f"{field} must be a valid integer."

        int_fields_non_negative = {
            "calves": "calves must be greater than or equal to 0.",
            "milking_cows": "milking_cows must be greater than or equal to 0.",
        }
        for field, msg in int_fields_non_negative.items():
            value = data.get(field)
            if value is None or value == "":
                errors[field] = f"{field} is required."
            else:
                try:
                    ival = int(value)
                    if ival < 0:
                        errors[field] = msg
                except (ValueError, TypeError):
                    errors[field] = f"{field} must be a valid integer."

        # --- Decimal fields ---
        tdm = data.get("TDM")
        if tdm is None or tdm == "":
            errors["TDM"] = "TDM is required."
        else:
            try:
                dval = float(tdm)
                if dval < 0:
                    errors["TDM"] = "TDM must be greater than or equal to 0."
            except (ValueError, TypeError):
                errors["TDM"] = "TDM must be a valid decimal number."

        # --- Enum fields ---
        ODKValidationService._validate_enum(data, "housing", ODKValidationService.FARM_HOUSING_TYPES, errors)
        ODKValidationService._validate_enum(data, "floor", ODKValidationService.FARM_FLOOR_TYPES, errors)
        ODKValidationService._validate_enum(data, "feed", ODKValidationService.FARM_FEED_TYPES, errors)
        ODKValidationService._validate_enum(data, "feeding_rate", ODKValidationService.FARM_FEEDING_RATES, errors)
        ODKValidationService._validate_enum(data, "water_source", ODKValidationService.FARM_WATER_SOURCES, errors)
        ODKValidationService._validate_enum(data, "water_rate", ODKValidationService.FARM_WATER_RATES, errors)
        ODKValidationService._validate_enum(data, "hygiene_score", ODKValidationService.FARM_HYGIENE_SCORES, errors)

        # --- Duplicate check: farm_id uniqueness in pending submissions and live Farms ---
        farm_id = data.get("farm_id", "").strip()
        if farm_id:
            from .models import Farm
            live_exists = Farm.objects.filter(farm_id=farm_id).exists()
            pending_exists = DataCollectorSubmission.objects.filter(
                form_type=DataCollectorSubmission.FormType.FARM,
                status=DataCollectorSubmission.Status.PENDING,
                submitted_data__farm_id=farm_id,
            ).exists()
            if live_exists or pending_exists:
                errors["farm_id"] = f"Farm with ID '{farm_id}' already exists."

        return errors

    @staticmethod
    def validate_animal_submission(data: Dict[str, Any]) -> Dict[str, str]:
        """Validate animal data collection submission against all ODK constraints.

        Args:
            data: Dictionary of submitted form fields.

        Returns:
            Dictionary of field_name -> error_message. Empty dict = valid.
        """
        errors = {}

        # --- Required identifiers ---
        for field in ("farm_id_input", "cow_id_input"):
            value = data.get(field)
            if not value or not str(value).strip():
                errors[field] = f"{field} is required."

        # --- Breed ---
        ODKValidationService._validate_enum(data, "breed", ODKValidationService.ANIMAL_BREEDS, errors)
        # Conditional: other_breed required when breed=other
        ODKValidationService._validate_conditional_required(
            data, "other_breed", "breed", "other", errors
        )

        # --- Date of birth ---
        dob = data.get("date_of_birth")
        if not dob:
            errors["date_of_birth"] = "date_of_birth is required."
        else:
            ODKValidationService._validate_date("date_of_birth", dob, errors)

        # --- Sex ---
        sex = data.get("sex")
        if sex is None or sex == "":
            errors["sex"] = "sex is required."
        elif str(sex).lower() != "f":
            errors["sex"] = "sex must be 'F'."

        # --- Parity ---
        ODKValidationService._validate_int_ge(data, "parity", 0, errors, required=True)

        # --- Body weight ---
        ODKValidationService._validate_decimal_gt(data, "body_weight", 0, errors, required=True)

        # --- BCS ---
        ODKValidationService._validate_enum(data, "bcs", ODKValidationService.ANIMAL_BCS_VALUES, errors)

        # --- Gynecological status ---
        ODKValidationService._validate_enum(
            data, "gynecological_status_name", ODKValidationService.ANIMAL_GYN_STATUSES, errors
        )

        # --- Lactation number ---
        ODKValidationService._validate_enum(
            data, "lactation_number", ODKValidationService.ANIMAL_LACTATION_NUMBERS, errors
        )

        # --- Has lameness ---
        ODKValidationService._validate_yes_no(data, "has_lameness", errors)

        # --- Days in milk ---
        ODKValidationService._validate_int_ge(data, "days_in_milk", 0, errors, required=True)

        # --- Average daily milk ---
        ODKValidationService._validate_decimal_ge(data, "average_daily_milk", 0, errors, required=True)

        # --- Cow inseminated before ---
        ODKValidationService._validate_yes_no(data, "cow_inseminated_before", errors)

        # --- Conditional: insemination fields ---
        insem_condition = data.get("cow_inseminated_before", "").strip().lower() == "yes"
        ODKValidationService._validate_conditional_required(
            data, "last_date_insemination", "cow_inseminated_before", "yes", errors
        )
        if insem_condition:
            ODKValidationService._validate_date("last_date_insemination", data.get("last_date_insemination"), errors)
            ODKValidationService._validate_int_ge(data, "number_of_inseminations", 0, errors, required=True)
            # id_or_breed_bull_used is optional even when relevant

        # --- Last calving date (optional) ---
        lcd = data.get("last_calving_date")
        if lcd:
            ODKValidationService._validate_date("last_calving_date", lcd, errors)

        # --- Is pregnant ---
        ODKValidationService._validate_yes_no(data, "is_pregnant", errors)

        # --- Conditional: pregnancy fields ---
        is_pregnant = data.get("is_pregnant", "").strip().lower() == "yes"
        ODKValidationService._validate_conditional_required(
            data, "pregnancy_date", "is_pregnant", "yes", errors
        )
        if is_pregnant and data.get("pregnancy_date"):
            ODKValidationService._validate_date("pregnancy_date", data.get("pregnancy_date"), errors)

        # --- Conditional: NSC (optional when pregnant) ---
        if is_pregnant:
            nsc = data.get("nsc")
            if nsc is not None and nsc != "":
                ODKValidationService._validate_int_ge(data, "nsc", 0, errors, required=False)

        # --- Conditional: heat shown (when not pregnant) ---
        not_pregnant = data.get("is_pregnant", "").strip().lower() == "no"
        if not_pregnant:
            ODKValidationService._validate_yes_no_in(data, "heat_shown", errors)
            heat_shown = data.get("heat_shown", "").strip().lower() == "yes"
            if heat_shown:
                ODKValidationService._validate_conditional_required(
                    data, "heat_start_date", "heat_shown", "yes", errors
                )
                ODKValidationService._validate_date("heat_start_date", data.get("heat_start_date"), errors)
                ODKValidationService._validate_conditional_required(
                    data, "heat_end_date", "heat_shown", "yes", errors
                )
                ODKValidationService._validate_date("heat_end_date", data.get("heat_end_date"), errors)
                ODKValidationService._validate_conditional_required(
                    data, "heat_signs", "heat_shown", "yes", errors
                )

        # --- Health statuses ---
        ODKValidationService._validate_enum(data, "udder_health", ODKValidationService.ANIMAL_UDDER_HEALTH, errors)
        ODKValidationService._validate_enum(data, "mastitis", ODKValidationService.ANIMAL_MASTITIS, errors)
        ODKValidationService._validate_enum(data, "general_health", ODKValidationService.ANIMAL_GENERAL_HEALTH, errors)
        ODKValidationService._validate_enum(
            data, "reproductive_health", ODKValidationService.ANIMAL_REPRODUCTIVE_HEALTH, errors
        )
        ODKValidationService._validate_conditional_required(
            data, "other_reproductive_health", "reproductive_health", "other", errors
        )
        ODKValidationService._validate_enum(
            data, "metabolic_disease", ODKValidationService.ANIMAL_METABOLIC_DISEASE, errors
        )
        ODKValidationService._validate_conditional_required(
            data, "other_metabolic_disease", "metabolic_disease", "other", errors
        )

        # --- Vaccination ---
        ODKValidationService._validate_yes_no(data, "is_vaccinated", errors)
        is_vaccinated = data.get("is_vaccinated", "").strip().lower() == "yes"
        ODKValidationService._validate_conditional_required(
            data, "vaccination_date", "is_vaccinated", "yes", errors
        )
        if is_vaccinated and data.get("vaccination_date"):
            ODKValidationService._validate_date("vaccination_date", data.get("vaccination_date"), errors)
        ODKValidationService._validate_conditional_required(
            data, "vaccination_type", "is_vaccinated", "yes", errors
        )

        # --- Deworming ---
        ODKValidationService._validate_yes_no(data, "deworming", errors)
        is_dewormed = data.get("deworming", "").strip().lower() == "yes"
        ODKValidationService._validate_conditional_required(
            data, "deworming_date", "deworming", "yes", errors
        )
        if is_dewormed and data.get("deworming_date"):
            ODKValidationService._validate_date("deworming_date", data.get("deworming_date"), errors)
        ODKValidationService._validate_conditional_required(
            data, "deworming_type", "deworming", "yes", errors
        )

        # --- Duplicate check: farm_id_input + cow_id_input uniqueness in pending submissions and live Cows ---
        farm_id = data.get("farm_id_input", "").strip()
        cow_id = data.get("cow_id_input", "").strip()
        if farm_id and cow_id:
            from .models import Cow
            live_exists = Cow.objects.filter(
                farm__farm_id=farm_id, cow_id=cow_id
            ).exists()
            pending_exists = DataCollectorSubmission.objects.filter(
                form_type=DataCollectorSubmission.FormType.ANIMAL,
                status=DataCollectorSubmission.Status.PENDING,
                submitted_data__farm_id_input=farm_id,
                submitted_data__cow_id_input=cow_id,
            ).exists()
            if live_exists or pending_exists:
                errors["cow_id_input"] = (
                    f"Cow with ID '{cow_id}' on farm '{farm_id}' already exists."
                )

        return errors

    # --- Helper methods ---

    @staticmethod
    def _validate_enum(data, field, valid_values, errors):
        """Validate that a field value is one of the allowed enum values."""
        value = data.get(field)
        if value is None or value == "":
            errors[field] = f"{field} is required."
        elif str(value).strip().lower() not in valid_values:
            errors[field] = f"{field} must be one of: {', '.join(sorted(valid_values))}."

    @staticmethod
    def _validate_yes_no(data, field, errors):
        """Validate that a field is 'yes' or 'no'."""
        value = data.get(field)
        if value is None or value == "":
            errors[field] = f"{field} is required."
        elif str(value).strip().lower() not in ("yes", "no"):
            errors[field] = f"{field} must be 'yes' or 'no'."

    @staticmethod
    def _validate_yes_no_in(data, field, errors):
        """Validate required field without default — value must be yes/no (for conditional fields)."""
        value = data.get(field)
        if value is not None and value != "":
            if str(value).strip().lower() not in ("yes", "no"):
                errors[field] = f"{field} must be 'yes' or 'no'."

    @staticmethod
    def _validate_conditional_required(data, target_field, condition_field, expected_value, errors):
        """Validate that target_field is required when condition_field equals expected_value."""
        condition_value = data.get(condition_field)
        if condition_value is not None and str(condition_value).strip().lower() == expected_value:
            target_value = data.get(target_field)
            if target_value is None or target_value == "":
                errors[target_field] = (
                    f"{target_field} is required when {condition_field} is '{expected_value}'."
                )

    @staticmethod
    def _validate_int_ge(data, field, minimum, errors, required=True):
        """Validate that a field is an integer >= minimum."""
        value = data.get(field)
        if value is None or value == "":
            if required:
                errors[field] = f"{field} is required."
            return
        try:
            ival = int(value)
            if ival < minimum:
                errors[field] = f"{field} must be greater than or equal to {minimum}."
        except (ValueError, TypeError):
            errors[field] = f"{field} must be a valid integer."

    @staticmethod
    def _validate_decimal_ge(data, field, minimum, errors, required=True):
        """Validate that a field is a decimal >= minimum."""
        value = data.get(field)
        if value is None or value == "":
            if required:
                errors[field] = f"{field} is required."
            return
        try:
            dval = float(value)
            if dval < minimum:
                errors[field] = f"{field} must be greater than or equal to {minimum}."
        except (ValueError, TypeError):
            errors[field] = f"{field} must be a valid decimal number."

    @staticmethod
    def _validate_decimal_gt(data, field, minimum, errors, required=True):
        """Validate that a field is a decimal > minimum."""
        value = data.get(field)
        if value is None or value == "":
            if required:
                errors[field] = f"{field} is required."
            return
        try:
            dval = float(value)
            if dval <= minimum:
                errors[field] = f"{field} must be greater than {minimum}."
        except (ValueError, TypeError):
            errors[field] = f"{field} must be a valid decimal number."

    @staticmethod
    def _validate_date(field, value, errors):
        """Validate that a value is a parseable date (YYYY-MM-DD)."""
        if not value:
            return
        from datetime import datetime
        if isinstance(value, str):
            try:
                datetime.strptime(value.strip(), "%Y-%m-%d")
            except ValueError:
                errors[field] = f"{field} must be a valid date in YYYY-MM-DD format."
        else:
            # Assume date/datetime object
            if not hasattr(value, "strftime"):
                errors[field] = f"{field} must be a valid date."
