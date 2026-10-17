d = {'1' : [{'23':2},{'99':454}]}
for x in d:
    for i in d[x]:
        if i.values() == '23':
            l = 2
            print(i.values())