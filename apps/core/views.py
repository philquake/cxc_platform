from django.shortcuts import render


def home(request):
    subjects = [
        {
            "name": "Information Technology",
            "code": "IT",
            "description": "Master CXC IT concepts with lessons and practice.",
        },
        {
            "name": "Computer Science",
            "code": "CS",
            "description": "Build your understanding of programming and computing.",
        },
        {
            "name": "Mathematics",
            "code": "MATH",
            "description": "Practice the concepts and skills needed for CXC Mathematics.",
        },
        {
            "name": "Biology",
            "code": "BIO",
            "description": "Learn biology through structured lessons and quizzes.",
        },
        {
            "name": "Chemistry",
            "code": "CHEM",
            "description": "Build your chemistry knowledge with targeted practice.",
        },
        {
            "name": "Physics",
            "code": "PHYS",
            "description": "Understand physics concepts and prepare for exams.",
        },
    ]

    return render(
        request,
        "core/home.html",
        {
            "subjects": subjects,
        },
    )