# Digital Twin

### Simple definition

A **Digital Twin** is a system where data flows between an existing **physical object** and a **digital object**.
The digital object act as a replica of the physical one which means that when a change is made in
the physical object, it automatically changes the state of the digital object and vice versa.

### Model

One important key feature of the Digital Twin is the notion of model.
The model is a representation of the physical object that is used to simulate its behavior and performance.
The model **doesn't need to be a perfect replica of the physical object**, but it should be able
to capture the key features and behaviors of the physical object.
In our case of a digital twin of a Plant, we will capture variables such as
temperature, soil moisture, humidity, light intensity or growth rate.

While the model need to be a good representation, it doesn't mean that it has to be complex.
The model needs to be as good as we are able to replace the physical object with the digital one
(in a limited context e.g temperature, humidity, etc.) and to be able to predict the behavior of the physical object
with good accuracy.
