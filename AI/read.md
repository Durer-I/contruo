This folder contains the basic logic that I have come up with for our auto takeoff and AI capapbilities.

below is a break down of what the operations look like so far:

### Title Block Namer:
- We ask user to mark an area whcih houses the title of the drawinghs sheets and extract the names
- we save these names for fututre analysis adn also as thumbnail names
- this feature still needs refining to be done


### Schedule adn Drawing finder:
- From the extartced shgeet names, we identify sheets which has "schedules" , "legends" , "floor plans", etc in their name:
    - allowing us to identify sheets which may have important data for out auto takeoff
- this feature still needs refining to be done

### Tables:
- We are currently using the pdfplumbers extarct table operation to find the tables on a given sheet.(sheets identified form the name filter discussed above)
- once a table is identified, we extract it adn save it.
- Then the intended use is to find the column which houses the tag value for an equipment, floor finish, door tag, etc..
    - once the tags are identified, we will run a global search throiugh the drawinsga dn find that respective tag and mark it adn add it to our quantities for our autotakeoff.
- this feature still needs refining to be done

### Walls adn Rooms
- Currently we are using pdfplumbers lines and rectangles properties to identifie different lines and rectangles on a given sheet (identified from the name filter discussed above)
- once identified we run different filters to identify which could be walls from the idnetified lines and rectangles
- once that is completed, we use opencv to fill the rooms with different colors
- then we mark it in quantities for our auto takeoff
- this feature still needs refining to be done

### Legend finder
- From sheets which has legends, we identify their location adn crop the legends to save them as a template
- From those templeate we identify which locations on the drawing sheet has that legend and we fill it with a color
- then we mark it in quantities for our auto takeoff.
- this feature still needs refining to be done