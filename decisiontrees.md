README: Regular Decision Trees (From Zero)

This README explains what a regular decision tree is, how it trains, what a split is, why we compute Gini impurity, and how predictions work — with a concrete example mindset.

1) What is a decision tree?

A decision tree is a flowchart that predicts an answer by asking a sequence of simple questions.
Example questions:

“Is hours_studied <= 3.5?”

“Is practice_tests <= 0.5?”

Each question sends your example down the YES or NO branch until you reach a leaf (an end node) that outputs the prediction.

2) What data do you need?

Your training data must be in a table format:

Each row = one example (one person / one case)

Each column = one feature (input information)

One final column = the label/target you want to predict

Example (classification):

Features: hours_studied, practice_tests

Target: pass (0 or 1)

3) Key vocabulary
Node

A place in the tree that contains a set of training rows.

Split

A single question that divides the rows in a node into two groups:

Left group = rows where the answer is YES

Right group = rows where the answer is NO

Example split:

“Is hours_studied <= 3.5?”

Leaf

A node where the tree stops splitting and stores a final prediction.

For classification:

leaf predicts the majority class in that leaf

(often also stores probabilities, like “80% pass, 20% fail”)

4) What does “training” mean for a regular decision tree?

Training is the process of building the flowchart.

At each node, the algorithm does the same loop:

Try every feature

hours_studied

practice_tests

etc.

Try candidate cutoffs for that feature

For numeric features: cutoffs come from values in the training data
Example: if you have hours values 1, 2, 3, 4, the candidates are 1.5, 2.5, 3.5 (midpoints between observed values)

Score each candidate split

For classification, the most common score is Gini impurity

The score tells how mixed each group is after the split

Pick the best split

Best means: the split that makes the data “cleanest” overall (lowest weighted impurity)

Repeat on child nodes

Keep splitting the side(s) that are still mixed

Stop when a stopping rule is met
Common stopping rules:

the node is already pure (all 0s or all 1s)

max depth reached

too few rows to split further

no split improves the score enough

That’s training.

5) Who chooses the cutoff?

The training algorithm chooses it automatically.

For a numeric feature like hours_studied:

Look at values in the current node (example: 1, 2, 2, 3, 4…)

Sort unique values (example: 1, 2, 3, 4…)

Try cutoffs between neighbors:

between 1 and 2 → 1.5

between 2 and 3 → 2.5

between 3 and 4 → 3.5

Then it scores each candidate cutoff and chooses the best.

6) Why do we compute Gini impurity?

Because the tree needs a consistent way to measure “how mixed” a group is.

If a node is all pass (all 1s) → perfectly clean → Gini = 0

If a node is half pass half fail → very mixed → Gini is high

The tree uses Gini to compare different split questions and pick the one that makes the children nodes the cleanest.

How Gini is used during training

For a candidate split:

compute Gini for the left group

compute Gini for the right group

combine them using a weighted average (weights = group sizes)

The tree chooses the split with the lowest weighted Gini.

7) How prediction works after training

To predict for a new row:

Start at the root question

Answer YES/NO based on that row’s feature values

Follow the branch

Repeat until a leaf

Output the leaf’s stored prediction

8) What’s the “shape” of a decision tree model?

A trained tree is literally a list of:

feature name

cutoff

left child pointer

right child pointer

leaf predictions

Conceptually:

Question 1?
  YES -> Question 2?
            YES -> leaf prediction
            NO  -> leaf prediction
  NO  -> leaf prediction

9) Common pitfalls (what beginners should know)

A single decision tree can overfit if it grows too deep.

Controlling depth and minimum leaf size helps it generalize.

Different split scores exist (Gini vs entropy), but the training loop is the same idea.