stu_sum = 5
grades = ["A", "B", "C", "D", "E"]
my_dict = {
    "number_{i}".format(i=i): "grade_{grade}".format(grade=grades[i]) for i in range(stu_sum)
}

print(my_dict)
