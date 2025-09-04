from CaseBrief import CaseBriefs

if __name__ == "__main__":
    cases = CaseBriefs()
    cases.load_cases_sql()
    for case in cases.case_briefs:
        print(f"Loaded case: {case.label.text} - {case.plaintiff} v. {case.defendant}")
