project_creation_ticket_fields = { 
            "DATASECURITY": {
                "type":  "dropdown", 
                "input_name": "customfield_10550",
                "output_name": "DATASECURITY", 
                "mandatory": True
            },

            # customfield_10611
            "PROJECT_TYPE": {
                "type":  "dropdown", 
                "input_name": "customfield_10611",
                "output_name": "PROJECT_TYPE",
                "mandatory": True

            },

            # customfield_10611
            "PROJECT_TYPE_FOLDER": {
                "type":  "dropdown_nested",
                "input_name": "customfield_10611",
                "output_name": "PROJECT_TYPE_FOLDER",
                "mandatory": True

            },

            "ENVIRONMENT": {
                "type":  "checklist", 
                "input_name": "customfield_10549",
                "output_name": "ENVIRONMENT",
                "mandatory": True

            },

            "BUDGET_DEV": {
                "type": "numericfield",
                "input_name": "customfield_10579",
                "output_name": "BUDGET_DEV",
                "validation": r"^[0-9]{1,10}\.[0-9]{1,5}$",
                "regex_error_message": "'BUDGET_DEV' must be a numeric value with up to 10 digits before and 5 digits after the decimal point.",
                "mandatory": False

            },

            "BUDGET_TEST": {
                "type": "numericfield",
                "input_name": "customfield_10613",
                "output_name": "BUDGET_TEST",
                "validation": r"^[0-9]{1,10}\.[0-9]{1,5}$",
                "regex_error_message": "'BUDGET_TEST' must be a numeric value with up to 10 digits before and 5 digits after the decimal point.",
                "mandatory": False

            },

            "BUDGET_PROD": {
                "type": "numericfield",
                "input_name": "customfield_10614",
                "output_name": "BUDGET_PROD",
                "validation": r"^[0-9]{1,10}\.[0-9]{1,5}$",
                "regex_error_message": "'BUDGET_PROD' must be a numeric value with up to 10 digits before and 5 digits after the decimal point.",
                "mandatory": False

            },
            # ticket creator: customfield_10461

            "PROJECT_NAME": {
                "type": "textfield",
                "input_name": "customfield_10551",
                "output_name": "PROJECT_NAME",
                "validation": r"^[0-9A-Za-z-_]{3,50}$",  # validate that the name is no longer than 10 char
                                                    # validate that the name is unique,
                'regex_error_message': "Project names should be alphanumeric (letters, numbers, '-', '_') and between 3 and 50 characters.",
                "mandatory": True

            },

            "FOLDER_NAME": {
                "type": "textfield",
                "input_name": "customfield_10578",
                "output_name": "FOLDER_NAME",
                "validation": r"^[0-9A-Za-z-_]{3,30}$", # up to 30 chars, need to be unique
                                                    # validate that the folder exists already
                'regex_error_message': "'FOLDER_NAME' must be alphanumeric (letters, numbers, '-', '_') and between 3 and 30 characters long.",
                "mandatory": True


            },

            "WBS": { # commessa
                "type": "textfield",
                "input_name": "customfield_10644",
                "output_name": "WBS",
                "validation": r"^[0-9A-Za-z-_]{3,100}$", # up to 30 chars, need to be unique
                                                    # validate that the folder exists already
                'regex_error_message': "'WBS' must be alphanumeric (letters, numbers, '-', '_') and between 3 and 100 characters long.",
                "mandatory": False


            },
                
            "ENGAGEMENT_MANAGER": {
                "type":  "reporter", 
                "input_name": "reporter",
                "output_name": "ENGAGEMENT_MANAGER",
                "mandatory": False            
                },

            # "ENGAGEMENT_MANAGER": {
            #         "type":  "people", 
            #         "input_name": "customfield_10461",
            #         "output_name": "ENGAGEMENT_MANAGER"            
            #     },
}


folder_creation_ticket_fields = { 

            # customfield_10611
            "PROJECT_TYPE": {
                "type":  "dropdown", 
                "input_name": "customfield_10611",
                "output_name": "PROJECT_TYPE",
                "mandatory": True

            },

            # customfield_10611
            "PROJECT_TYPE_FOLDER": {
                "type":  "dropdown_nested",
                "input_name": "customfield_10611",
                "output_name": "PROJECT_TYPE_FOLDER",
                "mandatory": True

            },


            "FOLDER_NAME": {
                "type": "textfield",
                "input_name": "customfield_10578",
                "output_name": "FOLDER_NAME",
                "validation": r"^[0-9A-Za-z-_]{3,30}$", # up to 30 chars, need to be unique
                                                    # validate that the folder exists already
                'regex_error_message': "'FOLDER_NAME' must be alphanumeric (letters, numbers, '-', '_') and between 3 and 30 characters long.",
                "mandatory": True


            },

            "WBS": { # commessa
                "type": "textfield",
                "input_name": "customfield_10644",
                "output_name": "WBS",
                "validation": r"^[0-9A-Za-z-_]{3,100}$", # up to 30 chars, need to be unique
                                                    # validate that the folder exists already
                'regex_error_message': "'WBS' must be alphanumeric (letters, numbers, '-', '_') and between 3 and 100 characters long.",
                "mandatory": False


            },
                
            "ENGAGEMENT_MANAGER": {
                "type":  "reporter", 
                "input_name": "reporter",
                "output_name": "ENGAGEMENT_MANAGER",
                "mandatory": False            
                },

            # "ENGAGEMENT_MANAGER": {
            #         "type":  "people", 
            #         "input_name": "customfield_10461",
            #         "output_name": "ENGAGEMENT_MANAGER"            
            #     },
}


data_security_mapping = {
    "l0": "tagValues/281478635840395",
    "l1": "tagValues/281481147692528",
    "l3": "tagValues/281476741727885"
}


env_mapping = {
    "dev": "Development",
    "test": "Test",
    "prod": "Production"
}