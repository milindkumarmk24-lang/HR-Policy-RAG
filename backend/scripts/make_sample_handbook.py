"""Generate the sample employee handbook used by the demo, tests and golden set.

Lumora Technologies is a FICTIONAL company. Every name, number and e-mail
address below is invented so the bot has a realistic, verifiable document to
answer from. Re-run this script only if you change the content: the golden
set's page numbers depend on the layout.

    python scripts/make_sample_handbook.py
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(__file__).resolve().parents[1] / "data" / "sample" / "Lumora_Employee_Handbook_2026.pdf"

COMPANY = "Lumora Technologies Pvt. Ltd."
HEADER = "Lumora Technologies - Employee Handbook 2026"

# --------------------------------------------------------------------------- #
# Content. ("h1", text) starts a chapter on a new page, ("h2", text) a section,
# ("p", text) a paragraph, ("ul", [items]) a bullet list, ("table", rows).
# --------------------------------------------------------------------------- #
CONTENT: list[tuple] = [
    ("h1", "1. Welcome and About This Handbook"),
    ("h2", "1.1 Purpose"),
    ("p", "This handbook explains the policies, benefits and standards of conduct that apply to everyone who works at "
          "Lumora Technologies Pvt. Ltd. (\"Lumora\" or \"the Company\"). It is a guide, not a contract of employment. "
          "Where this handbook and your appointment letter differ, your appointment letter prevails. Where either differs "
          "from applicable Indian law, the law prevails."),
    ("h2", "1.2 Who This Handbook Applies To"),
    ("p", "The handbook applies to all full-time and part-time employees, fixed-term contract employees and interns working "
          "from any Lumora office in India, unless a section says otherwise. Consultants engaged through third-party "
          "agencies are covered only by Chapter 8 (Code of Conduct), Chapter 9 (Prevention of Sexual Harassment) and "
          "Chapter 12 (Information Security)."),
    ("h2", "1.3 Effective Date and Updates"),
    ("p", "This edition is effective from 1 April 2026 and replaces all earlier editions. The People Team reviews the "
          "handbook every year in March. Changes are announced by e-mail and published on PeopleDesk, the Company's HR "
          "portal, at least 15 days before they take effect, except where a change is required by law."),
    ("h2", "1.4 Getting Help"),
    ("p", "If something in this handbook is unclear, ask your manager or your HR Business Partner (HRBP) first. You can "
          "also raise a ticket on PeopleDesk or write to the HR helpdesk at hr-help@lumora.example. The helpdesk responds "
          "within 2 working days. Contact details for every team mentioned in this handbook are listed in Chapter 14."),

    ("h1", "2. Employment Basics"),
    ("h2", "2.1 Employment Categories"),
    ("ul", [
        "<b>Full-time employees</b> work the standard 40-hour week and are eligible for all benefits in this handbook.",
        "<b>Part-time employees</b> work between 20 and 30 hours a week. Leave entitlements are pro-rated to hours worked.",
        "<b>Fixed-term contract employees</b> are hired for a defined period of up to 24 months. They receive leave and "
        "health insurance but are not eligible for the annual performance bonus.",
        "<b>Interns</b> are engaged for 2 to 6 months and receive a monthly stipend. Interns receive 1 day of paid leave "
        "for each completed month of internship and are covered by group health insurance for themselves only.",
    ]),
    ("h2", "2.2 Probation and Confirmation"),
    ("p", "All new full-time employees serve a probation period of 6 months from their date of joining. During probation, "
          "your manager will hold check-in conversations at the end of month 2 and month 4. If your performance is "
          "satisfactory, you will receive a confirmation letter within 15 days of completing probation. The Company may "
          "extend probation once, by up to 3 months, if more time is needed to assess performance. You will be told of "
          "any extension in writing before the original probation period ends."),
    ("h2", "2.3 Working Hours and Attendance"),
    ("p", "The standard working week is Monday to Friday, 40 hours, with a daily one-hour meal break that is not counted "
          "as working time. Lumora follows flexible hours: you may start work at any time between 8:00 a.m. and 11:00 a.m., "
          "but you are expected to be available during core hours of 11:00 a.m. to 4:00 p.m. Record your attendance "
          "on PeopleDesk every working day. Three or more unrecorded days in a calendar month are treated as unplanned "
          "absence and your manager will discuss them with you."),
    ("h2", "2.4 Notice Period"),
    ("p", "The notice period depends on your status and level:"),
    ("table", [
        ["Status / level", "Notice period (either side)"],
        ["During probation", "15 days"],
        ["Confirmed employees, levels L1 to L4", "60 days"],
        ["Confirmed employees, level L5 and above (managers)", "90 days"],
        ["Interns", "7 days"],
    ]),
    ("p", "Resignation and the rules for serving or buying out notice are covered in Chapter 13."),

    ("h1", "3. Leave Policy"),
    ("h2", "3.1 Leave Year and General Rules"),
    ("p", "The leave year runs from 1 January to 31 December. Apply for all leave on PeopleDesk. Planned leave of more "
          "than 3 consecutive working days must be applied for at least 7 days in advance. Unplanned leave, such as "
          "sickness, must be reported to your manager by 10:00 a.m. on the first day of absence and applied for on "
          "PeopleDesk within 2 working days of returning. Weekends and public holidays that fall within a period of "
          "leave are not counted as leave days, except for maternity, adoption and sabbatical leave, which are counted "
          "in calendar weeks or months."),
    ("p", "The table below summarises annual entitlements for full-time employees. Each type is explained in the sections "
          "that follow."),
    ("table", [
        ["Leave type", "Entitlement per year", "Carry forward"],
        ["Earned leave (EL)", "18 working days", "Up to 30 days"],
        ["Casual leave (CL)", "8 working days", "None"],
        ["Sick leave (SL)", "10 working days", "Up to 20 days"],
        ["Public holidays", "10 fixed + 2 optional", "Not applicable"],
        ["Paternity leave", "10 working days per child", "Not applicable"],
        ["Maternity leave", "26 weeks (first two children)", "Not applicable"],
    ]),
    ("h2", "3.2 Earned Leave"),
    ("p", "Full-time employees earn 18 working days of earned leave (EL) a year, credited at 1.5 days at the end of each "
          "completed month of service. You can use earned leave from your date of joining, but you cannot take more "
          "than you have accrued. At the end of the leave year, up to 30 days of unused earned leave carry forward to the "
          "next year; any balance above 30 days lapses. On leaving the Company, you will be paid for up to 15 days of "
          "unused earned leave at your basic salary; any balance beyond 15 days is not paid out."),
    ("h2", "3.3 Casual Leave"),
    ("p", "Casual leave (CL) covers short personal needs. You receive 8 working days of casual leave on 1 January each "
          "year, pro-rated for employees who join during the year. Casual leave cannot be taken for more than 3 "
          "consecutive working days, cannot be combined with earned leave, and does not carry forward: any unused "
          "balance lapses on 31 December. Casual leave is not paid out on separation."),
    ("h2", "3.4 Sick Leave"),
    ("p", "You receive 10 working days of sick leave (SL) each year for your own illness or injury. A medical certificate "
          "from a registered medical practitioner is required for sick leave of more than 2 consecutive working days. "
          "Unused sick leave carries forward up to a maximum accumulated balance of 20 days. Sick leave is not paid out "
          "on separation. If you have used all your sick leave, further absence due to illness is debited from earned "
          "leave and then treated as leave without pay."),
    ("h2", "3.5 Public Holidays"),
    ("p", "Lumora observes 10 fixed public holidays each year, published on PeopleDesk in December for the following year. "
          "In addition, you may choose 2 optional holidays from the list of restricted holidays to suit your own "
          "festivals or observances. Optional holidays must be selected on PeopleDesk at least 7 days in advance."),
    ("h2", "3.6 Compensatory Off"),
    ("p", "If your manager asks you to work on a weekend or public holiday, you earn one compensatory off (comp-off) day "
          "for each full day worked, or half a day for at least 4 hours worked. Comp-off must be approved by your manager "
          "on PeopleDesk before the work is done and must be used within 60 days of being earned, after which it lapses. "
          "Comp-off cannot be encashed."),

    ("h2", "3.7 Maternity Leave"),
    ("p", "Female employees who have worked for Lumora for at least 80 days in the 12 months before their expected date "
          "of delivery are entitled to 26 weeks of paid maternity leave for each of their first two children, of which up "
          "to 8 weeks may be taken before the expected date of delivery. For a third or subsequent child, maternity leave "
          "is 12 weeks. In the case of a miscarriage or medical termination of pregnancy, 6 weeks of paid leave is "
          "available immediately following the event. Apply for maternity leave on PeopleDesk at least 8 weeks before "
          "your intended start date and attach a medical certificate stating the expected date of delivery."),
    ("p", "After returning from maternity leave, you may request to work from home for up to 3 additional months where "
          "your role allows it, subject to your manager's approval. Lumora offices with 50 or more employees provide a "
          "creche facility or a creche allowance of Rs. 5,000 per month until the child turns 3."),
    ("h2", "3.8 Adoption and Surrogacy Leave"),
    ("p", "An employee who legally adopts a child below the age of 3 months, or a commissioning mother in a surrogacy "
          "arrangement, is entitled to 12 weeks of paid leave from the date the child is handed over. An employee who "
          "adopts a child aged 3 months or older is entitled to 6 weeks of paid leave."),
    ("h2", "3.9 Paternity Leave"),
    ("p", "Male employees and the non-birthing partner in any couple are entitled to 10 working days of paid paternity "
          "leave for each birth or adoption, up to a maximum of two children. Paternity leave must be taken within 6 "
          "months of the child's birth or adoption and can be taken in up to two blocks."),
    ("h2", "3.10 Bereavement Leave"),
    ("p", "In the event of the death of an immediate family member (spouse or partner, child, parent, sibling, or parent-"
          "in-law), you are entitled to 5 working days of paid bereavement leave. For the death of a grandparent or "
          "grandchild, you are entitled to 2 working days. Bereavement leave should be taken within 30 days of the death "
          "and does not require supporting documents unless requested by HR."),
    ("h2", "3.11 Marriage Leave"),
    ("p", "Confirmed employees receive 3 working days of paid marriage leave for their own wedding, once during their "
          "employment with Lumora. It must be taken within 3 months of the wedding date."),
    ("h2", "3.12 Leave Without Pay and Sabbatical"),
    ("p", "When all applicable paid leave is exhausted, you may request leave without pay (LWP) for up to 30 days in a "
          "leave year, with the approval of your manager and HRBP. LWP beyond 30 days requires approval from the Head "
          "of People. Employees with at least 5 years of continuous service may apply for an unpaid sabbatical of 1 to 3 "
          "months for study, caregiving or personal projects. Health insurance continues during a sabbatical, but leave "
          "does not accrue."),

    ("h1", "4. Compensation and Payroll"),
    ("h2", "4.1 Pay Date and Payslips"),
    ("p", "Salaries are paid by bank transfer on the last working day of each month. If the last working day is a bank "
          "holiday, salary is paid on the previous working day. Payslips are available on PeopleDesk by the 3rd of the "
          "following month. Report any payroll error to payroll@lumora.example within 30 days of the pay date."),
    ("h2", "4.2 Salary Structure"),
    ("p", "Your cost to company (CTC) is made up of basic salary (40% of fixed pay), house rent allowance (50% of basic "
          "salary), a flexible benefits component, the employer's provident fund contribution and, where applicable, a "
          "variable performance bonus. A breakdown is attached to your appointment letter and to each annual "
          "compensation letter."),
    ("h2", "4.3 Performance Reviews and Increments"),
    ("p", "Lumora's performance year runs from April to March. Annual performance reviews take place in April, and "
          "salary increments and promotions take effect from 1 July. Employees who joined after 1 January of the review "
          "year are reviewed but are not eligible for an increment until the next cycle. A mid-year check-in is held in "
          "October."),
    ("h2", "4.4 Performance Bonus"),
    ("p", "Full-time employees at levels L1 to L4 are eligible for an annual performance bonus with a target of up to 10% "
          "of fixed pay; employees at L5 and above have a target of up to 15%. The bonus depends on both Company and "
          "individual performance and is paid with the July salary. You must be on the Company's rolls on the payout date "
          "to receive the bonus, and employees serving notice are not eligible."),
    ("h2", "4.5 Salary Advance"),
    ("p", "Confirmed employees facing an emergency may request a salary advance of up to one month's net salary, once in "
          "any 12-month period. The advance is interest-free and is recovered in equal instalments over 6 months. Requests "
          "are submitted on PeopleDesk and approved by your HRBP and the Finance team."),

    ("h1", "5. Benefits"),
    ("h2", "5.1 Group Health Insurance"),
    ("p", "Lumora provides group medical insurance from your date of joining. The policy is a family floater with a sum "
          "insured of Rs. 5,00,000 per year covering you, your spouse or registered partner and up to two children under "
          "25 years of age. The premium for this cover is paid entirely by the Company. You may also add your parents or "
          "parents-in-law (but not both) under a separate parental cover of Rs. 3,00,000; the premium for parental cover "
          "is deducted from your salary."),
    ("p", "The policy covers hospitalisation, day-care procedures and pre- and post-hospitalisation expenses for 30 and 60 "
          "days respectively. Maternity expenses are covered up to Rs. 75,000 per delivery, and there is no waiting period "
          "for pre-existing conditions. Cashless treatment is available at network hospitals; for other hospitals, submit "
          "a reimbursement claim to the insurer within 30 days of discharge. Dependants must be added within 30 days of "
          "joining or of a life event such as marriage or birth; otherwise they can only be added at the annual renewal "
          "in April."),
    ("h2", "5.2 Life and Accident Insurance"),
    ("p", "All full-time employees are covered by group term life insurance of 3 times annual fixed CTC and group personal "
          "accident insurance of 5 times annual fixed CTC. Both are fully paid by the Company. Please keep your nominee "
          "details up to date on PeopleDesk."),
    ("h2", "5.3 Provident Fund and Gratuity"),
    ("p", "Lumora contributes 12% of your basic salary to the Employees' Provident Fund (EPF), and an equal 12% is deducted "
          "from your salary as your contribution. Gratuity is payable under the Payment of Gratuity Act, 1972 on "
          "separation after at least 5 years of continuous service, calculated as 15 days of last drawn basic salary for "
          "each completed year of service."),
    ("h2", "5.4 Wellness Benefits"),
    ("ul", [
        "<b>Annual health check-up:</b> employees aged 30 and above can take one free comprehensive health check-up each "
        "year at a partner diagnostic centre.",
        "<b>Employee Assistance Programme (EAP):</b> you and your dependants can access confidential counselling with up to "
        "6 free sessions per person per year. The Company does not learn who uses the EAP.",
        "<b>Fitness allowance:</b> Rs. 1,000 per month for gym memberships, sports or fitness apps, claimed through the "
        "flexible benefits plan.",
    ]),
    ("h2", "5.5 Learning and Development"),
    ("p", "Each full-time employee has a learning budget of Rs. 40,000 per financial year for courses, conferences and "
          "certifications related to their role, with prior approval from their manager. Certification exam fees are "
          "reimbursed only if you pass the exam. If you leave Lumora within 12 months of a reimbursement above "
          "Rs. 25,000, you must repay the amount on a pro-rated basis."),
    ("h2", "5.6 Hybrid Work Allowance"),
    ("p", "Employees on a hybrid or remote arrangement receive an internet allowance of Rs. 1,500 per month, paid with "
          "salary. A one-time home office setup reimbursement of up to Rs. 10,000 is available for a chair or desk, "
          "claimed within 6 months of joining or of moving to a hybrid arrangement."),
    ("h2", "5.7 Employee Referral Programme"),
    ("p", "If you refer a candidate who is hired, you receive a referral bonus of Rs. 50,000 for engineering and data roles "
          "and Rs. 25,000 for all other roles. The bonus is paid after the new employee completes 90 days with Lumora and "
          "while you are still employed. Referrals of former Lumora employees, and referrals by hiring managers for their "
          "own open roles, are not eligible."),

    ("h1", "6. Work Arrangements"),
    ("h2", "6.1 Hybrid Work"),
    ("p", "Lumora follows a hybrid model. Employees are expected to work from their assigned office at least 2 days a week, "
          "and Tuesdays and Thursdays are anchor days when teams meet in person. Teams may agree on additional office "
          "days. Employees in their probation period are expected to work from the office at least 3 days a week to help "
          "them settle in."),
    ("h2", "6.2 Remote Work"),
    ("p", "A fully remote arrangement requires approval from your department's Vice President and your HRBP, and is "
          "reviewed every 6 months. You may work from a city other than your base location for up to 30 working days in a "
          "calendar year with your manager's approval. Working from outside India, even temporarily, is not permitted "
          "without written approval from the People Team and Finance because of tax and data-protection obligations."),
    ("h2", "6.3 Overtime and Shifts"),
    ("p", "Employees in support roles who work rotational or night shifts receive a shift allowance of Rs. 300 per night "
          "shift worked between 10:00 p.m. and 6:00 a.m. The Company provides safe transport for employees whose shift "
          "starts or ends between 8:00 p.m. and 7:00 a.m. Regular work beyond 48 hours in a week requires approval from "
          "your manager and is compensated with comp-off as described in Section 3.6."),

    ("h1", "7. Travel and Expenses"),
    ("h2", "7.1 Booking Business Travel"),
    ("p", "All business travel must be approved by your manager on PeopleDesk before you book. Book flights, trains and "
          "hotels through the Company's travel desk at travel@lumora.example at least 7 days in advance for domestic "
          "travel and 21 days in advance for international travel. For domestic trips over 500 km you may travel by "
          "economy-class flight; for shorter trips, travel by AC 2-tier train or Company-approved cab."),
    ("h2", "7.2 Hotel Limits and Per Diem"),
    ("p", "Hotel stays are reimbursed up to the following limits per night, including taxes. A daily allowance (per diem) "
          "covers meals and incidental expenses, and you do not need receipts for it."),
    ("table", [
        ["Destination", "Hotel limit per night", "Per diem per day"],
        ["Tier 1 cities (Mumbai, Delhi NCR, Bengaluru)", "Rs. 6,000", "Rs. 1,200"],
        ["Tier 2 cities (Pune, Hyderabad, Chennai and others)", "Rs. 4,500", "Rs. 1,000"],
        ["Other domestic locations", "Rs. 3,000", "Rs. 800"],
        ["International travel", "USD 180", "USD 60"],
    ]),
    ("h2", "7.3 Submitting Expense Claims"),
    ("p", "Submit expense claims on PeopleDesk within 30 days of the expense or the end of your trip, with itemised "
          "receipts for every expense except per diem. Claims submitted after 30 days need approval from your "
          "department head, and claims older than 90 days will not be reimbursed. Any single claim above Rs. 5,000 needs "
          "approval from both your manager and the Finance team. Approved claims are reimbursed with the next salary "
          "payment."),
    ("h2", "7.4 Expenses That Are Not Reimbursed"),
    ("ul", [
        "Alcohol, except at Company-approved client events.",
        "Traffic fines, parking fines and penalties of any kind.",
        "Personal entertainment, such as in-room movies, spa services or minibar charges.",
        "Upgrades to a higher class of travel or hotel without prior approval.",
        "Costs of family members or friends who travel with you.",
    ]),

    ("h1", "8. Code of Conduct"),
    ("h2", "8.1 Our Standards"),
    ("p", "Everyone at Lumora is expected to act with honesty, treat colleagues, clients and partners with respect, and "
          "comply with the law. You are responsible for reading this chapter and for raising concerns when you see "
          "behaviour that does not meet these standards."),
    ("h2", "8.2 Conflicts of Interest"),
    ("p", "A conflict of interest arises when your personal interests could influence, or appear to influence, your work "
          "decisions. You must disclose any potential conflict to your manager and to compliance@lumora.example as soon as "
          "you become aware of it. Outside employment, freelancing or consulting (sometimes called moonlighting) requires "
          "prior written approval from your manager and HRBP, and is never allowed for a competitor, client or vendor of "
          "Lumora. Unpaid voluntary work and personal open-source projects that do not use Company resources or "
          "confidential information do not need approval."),
    ("h2", "8.3 Gifts and Hospitality"),
    ("p", "You may accept gifts or hospitality from clients, vendors or partners only if their value is Rs. 2,000 or less "
          "and they are not cash or cash equivalents such as gift cards. Any gift above Rs. 2,000 must be declared to "
          "Compliance within 7 days and may need to be returned or donated. Never accept a gift of any value from a "
          "vendor during an active procurement or tender process. Offering bribes or facilitation payments to anyone, "
          "including government officials, is strictly prohibited."),
    ("h2", "8.4 Confidentiality and Data Protection"),
    ("p", "You must protect the confidential information of Lumora, its clients and its employees, both during and after "
          "your employment. Share confidential information only with people who need it for their work, and never "
          "upload Company or client data to personal storage or to public AI tools that are not approved by the "
          "Information Security team."),
    ("h2", "8.5 Social Media"),
    ("p", "You may mention that you work at Lumora on personal social media, but you must not speak on behalf of the "
          "Company, share confidential information, or post content about clients without approval from the "
          "Communications team. Make it clear that your views are your own."),
    ("h2", "8.6 Dress Code"),
    ("p", "Lumora's dress code is business casual on regular office days. On Fridays, smart casual clothing is welcome. "
          "When meeting clients, follow the client's dress code or wear formal business attire."),
    ("h2", "8.7 Alcohol, Drugs and Smoking"),
    ("p", "Working under the influence of alcohol or illegal drugs is prohibited. Alcohol may be served only at "
          "Company-approved events. Smoking and vaping are permitted only in designated areas outside office buildings."),

    ("h1", "9. Prevention of Sexual Harassment (POSH)"),
    ("h2", "9.1 Our Commitment"),
    ("p", "Lumora has zero tolerance for sexual harassment. This policy follows the Sexual Harassment of Women at "
          "Workplace (Prevention, Prohibition and Redressal) Act, 2013, and the Company extends its protection to "
          "employees of all genders. It applies at the workplace, at offsite events, during business travel, and in "
          "online communication related to work."),
    ("h2", "9.2 Internal Committee"),
    ("p", "Each Lumora office has an Internal Committee (IC) chaired by a senior woman employee, with at least half of its "
          "members being women and one external member from an organisation working on women's rights. The names of IC "
          "members are displayed in every office and on PeopleDesk."),
    ("h2", "9.3 How to Raise a Complaint"),
    ("p", "A complaint should be made in writing to the Internal Committee at ic@lumora.example within 3 months of the "
          "incident, or of the last incident in a series. The IC may extend this time limit by a further 3 months if there "
          "were circumstances that prevented the complaint from being made earlier. If you need help writing the complaint, "
          "any IC member will assist you. You may also speak to your HRBP, who will connect you with the IC."),
    ("h2", "9.4 Inquiry and Outcome"),
    ("p", "The IC will complete its inquiry within 90 days of receiving a complaint, and the Company will act on its "
          "recommendations within 60 days of receiving the report. During the inquiry, the complainant may request interim "
          "measures such as a transfer or paid leave of up to 3 months. All proceedings are confidential. Retaliation "
          "against anyone who raises a complaint or takes part in an inquiry is itself misconduct and will lead to "
          "disciplinary action."),

    ("h1", "10. Grievances and Whistleblowing"),
    ("h2", "10.1 Raising a Grievance"),
    ("p", "If you have a concern about your work, working conditions or treatment, first try to resolve it with your "
          "manager. If that does not work, or if the concern is about your manager, raise it with your HRBP or through a "
          "PeopleDesk grievance ticket. HR will acknowledge the grievance within 5 working days and aim to resolve it within "
          "30 days. If you are not satisfied with the outcome, you may appeal to the Head of People within 15 days."),
    ("h2", "10.2 Whistleblower Policy"),
    ("p", "Report suspected fraud, bribery, financial misconduct, data breaches or serious violations of law or of this "
          "handbook through the Ethics Helpline at ethics@lumora.example or the confidential ethics portal on PeopleDesk, "
          "which accepts anonymous reports. Reports are reviewed by the Ethics Committee, which reports to the Audit "
          "Committee of the Board. Lumora protects whistleblowers who report in good faith from any retaliation, including "
          "dismissal, demotion or harassment."),

    ("h1", "11. Disciplinary Process"),
    ("h2", "11.1 Misconduct"),
    ("p", "Misconduct is any breach of this handbook, your appointment letter or the law. Minor misconduct includes "
          "repeated late attendance or failing to record attendance. Serious misconduct includes harassment, theft, fraud, "
          "violence, disclosure of confidential information, and working under the influence of alcohol or drugs."),
    ("h2", "11.2 Steps in the Process"),
    ("p", "For most issues, the process is progressive: a verbal warning, then a written warning, then a final written "
          "warning. Performance concerns are addressed through a Performance Improvement Plan (PIP) lasting 60 days, with "
          "fortnightly reviews. For alleged serious misconduct, the Company will issue a show-cause notice, and you must "
          "reply in writing within 3 working days. You may be suspended on full pay while an investigation is carried out. "
          "Serious misconduct, if proven, can result in termination without notice."),
    ("h2", "11.3 Your Rights"),
    ("p", "You will always be told the allegation against you, shown the evidence, and given a chance to respond before any "
          "decision is made. You may be accompanied by a colleague of your choice at any disciplinary hearing. You may "
          "appeal a disciplinary decision to the Head of People within 7 working days."),

    ("h1", "12. Information Security and IT"),
    ("h2", "12.1 Acceptable Use"),
    ("p", "Company laptops, accounts and networks are provided for work. Limited personal use is acceptable if it does not "
          "affect your work or the security of Company systems. Do not install unapproved software, and do not use personal "
          "USB storage devices on Company laptops."),
    ("h2", "12.2 Passwords and Access"),
    ("p", "Use a unique password of at least 14 characters for your Lumora account, and keep multi-factor authentication "
          "(MFA) switched on for every Company system. Never share your password, including with IT staff."),
    ("h2", "12.3 Reporting Incidents and Lost Devices"),
    ("p", "Report a suspected security incident, such as a phishing e-mail you clicked on or data sent to the wrong person, "
          "to security@lumora.example within 1 hour of noticing it. Report a lost or stolen laptop or phone that has "
          "Company data to the IT helpdesk within 24 hours so it can be wiped remotely. You will not be penalised for "
          "reporting an honest mistake promptly."),

    ("h1", "13. Resignation and Separation"),
    ("h2", "13.1 Resigning"),
    ("p", "To resign, submit your resignation on PeopleDesk and inform your manager. Your notice period, as set out in "
          "Section 2.4, starts on the day after your resignation is submitted. You may withdraw a resignation within 7 days "
          "of submitting it, with your manager's agreement."),
    ("h2", "13.2 Serving or Buying Out Notice"),
    ("p", "You are expected to serve your full notice period. The Company may, at its discretion, allow you to leave early "
          "by waiving part of the notice period or by accepting payment of basic salary in lieu of the unserved notice "
          "(a notice buyout). Earned leave cannot be used to shorten the notice period, except that up to 5 days of earned "
          "leave may be adjusted with your manager's approval. Leave taken during the notice period may extend your last "
          "working day."),
    ("h2", "13.3 Exit Process and Full and Final Settlement"),
    ("p", "Before your last working day, complete the handover agreed with your manager, return your laptop, ID card and "
          "any other Company property, and complete the exit interview with HR. Your full and final (F&amp;F) settlement, "
          "including salary up to your last working day, encashment of eligible earned leave and any other dues, less any "
          "recoveries, will be paid within 45 days of your last working day. Your relieving letter and experience letter "
          "are issued on the day the F&amp;F settlement is processed."),

    ("h1", "14. Contacts and Glossary"),
    ("h2", "14.1 Key Contacts"),
    ("table", [
        ["Team", "Contact", "Use it for"],
        ["HR helpdesk", "hr-help@lumora.example, ext. 4040", "General HR and policy questions"],
        ["Payroll", "payroll@lumora.example", "Salary, payslips and tax"],
        ["Travel desk", "travel@lumora.example", "Booking business travel"],
        ["Compliance", "compliance@lumora.example", "Conflicts of interest and gifts"],
        ["Internal Committee", "ic@lumora.example", "Sexual harassment complaints"],
        ["Ethics Helpline", "ethics@lumora.example", "Whistleblowing, including anonymous reports"],
        ["Information Security", "security@lumora.example", "Security incidents"],
    ]),
    ("h2", "14.2 Glossary"),
    ("ul", [
        "<b>CTC</b>: cost to company, the total annual cost of your employment, including benefits.",
        "<b>HRBP</b>: HR Business Partner, the HR contact assigned to your department.",
        "<b>LWP</b>: leave without pay.",
        "<b>PeopleDesk</b>: Lumora's HR portal for leave, attendance, payslips, claims and tickets.",
        "<b>PIP</b>: Performance Improvement Plan.",
        "<b>F&amp;F</b>: full and final settlement on leaving the Company.",
    ]),
    ("p", "<i>This is a sample handbook for a fictional company, created to demonstrate an HR policy assistant. It does not "
          "describe any real organisation's policies and is not legal advice.</i>"),
]


def build(out: Path = OUT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontName="Helvetica", fontSize=10.2, leading=14.2,
                          spaceAfter=6)
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=17, leading=21,
                        textColor=colors.HexColor("#1f3d36"), spaceAfter=10)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15,
                        textColor=colors.HexColor("#1f3d36"), spaceBefore=8, spaceAfter=4)
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=14, bulletIndent=4, spaceAfter=3)

    story: list = []
    # Cover page
    cover_title = ParagraphStyle("ct", parent=h1, fontSize=28, leading=34, alignment=TA_CENTER)
    cover_sub = ParagraphStyle("cs", parent=body, fontSize=13, leading=18, alignment=TA_CENTER,
                               textColor=colors.HexColor("#4a5a55"))
    story += [Spacer(1, 70 * mm), Paragraph("Employee Handbook", cover_title), Spacer(1, 6 * mm),
              Paragraph(COMPANY, cover_sub), Paragraph("Edition effective 1 April 2026", cover_sub),
              Spacer(1, 40 * mm),
              Paragraph("Sample document for a fictional company. For demonstration only.", cover_sub),
              PageBreak()]

    first_chapter = True
    for kind, value in CONTENT:
        if kind == "h1":
            if not first_chapter:
                story.append(PageBreak())
            first_chapter = False
            story.append(Paragraph(value, h1))
        elif kind == "h2":
            story.append(Paragraph(value, h2))
        elif kind == "p":
            story.append(Paragraph(value, body))
        elif kind == "ul":
            story += [Paragraph(item, bullet, bulletText="•") for item in value]
        elif kind == "table":
            cell = ParagraphStyle("cell", parent=body, fontSize=9.4, leading=12, spaceAfter=0)
            head = ParagraphStyle("head", parent=cell, fontName="Helvetica-Bold")
            rows = [[Paragraph(c, head if i == 0 else cell) for c in row] for i, row in enumerate(value)]
            ncols = len(value[0])
            width = 170 * mm
            t = Table(rows, colWidths=[width / ncols] * ncols, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6eeea")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9fb3ab")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story += [KeepTogether(t), Spacer(1, 6)]

    def on_page(canvas, doc):
        if doc.page == 1:
            return
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6b7a75"))
        canvas.drawString(20 * mm, A4[1] - 12 * mm, HEADER)
        canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=20 * mm, bottomMargin=18 * mm,
                            title="Lumora Technologies Employee Handbook 2026 (sample)",
                            author="Lumora Technologies (fictional)")
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return out


if __name__ == "__main__":
    path = build()
    print(f"Wrote {path}")
